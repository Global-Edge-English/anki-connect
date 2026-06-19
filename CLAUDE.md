# AnkiConnect GlobalEdge

## Project Overview

A customized fork of [AnkiConnect](https://foosoft.net/projects/anki-connect/) — an Anki add-on that exposes Anki functionality over a local HTTP API (port 8765). This version is branded "Global Edge Anki Connect" and adds study management, note management, and audio injection features on top of the original AnkiConnect.

- **Language:** Python (Anki add-on)
- **Current version:** defined in `manifest.json` and `AnkiConnect.py` (`ADDON_VERSION`)
- **API version:** 5

## Architecture

- `AnkiConnect.py` — Main entry point. HTTP request handler, API action dispatch, and core Anki operations.
- `managers/` — Domain logic split into:
  - `note_manager.py` — Note/card operations
  - `study_manager.py` — Study session and scheduling logic
- `utils/` — Shared helpers:
  - `helpers.py` — String utils, download, MIME type, audio injection
  - `network.py` — `AjaxServer` HTTP server implementation
  - `deck_helpers.py` — Deck-related utilities
- `tests/` — Test files (`test_answer_card.py`, `test_decks.py`, `test_misc.py`)

## Building

Run `build_zip.sh` to package the add-on. It:
1. Prompts for a version bump (updates `manifest.json` and `AnkiConnect.py`)
2. Copies `AnkiConnect.py` to `__init__.py`
3. Zips into `GlobalEdgeAnkiConnect.zip` using `7za`

## Development Notes

- The add-on runs inside Anki's Python environment (`anki`, `aqt` modules).
- Tests use a Docker-based setup (see `tests/docker/`).
- Keep import fallback chains in `AnkiConnect.py` intact — they handle different execution contexts.
- Version must stay in sync between `manifest.json` (`version` and `name` fields) and `AnkiConnect.py` (`ADDON_VERSION`). Use `build_zip.sh` to update.

## Performance patterns (use these before rolling your own)

These come up repeatedly in this codebase. Apply them when adding or
touching API endpoints — and call them out in code review.

### SQL: prefer INNER JOIN over `IN (SELECT ...)` for revlog/cards queries

The IN-subquery form forces SQLite to materialize the inner set and probe
per outer row. INNER JOIN lets it walk the revlog primary-key index and
join straight into cards. Replace:

```sql
WHERE id > ? AND cid IN (SELECT id FROM cards WHERE did IN (...))
```

with:

```sql
FROM revlog r INNER JOIN cards c ON r.cid = c.id
WHERE r.id > ? AND c.did IN (...)
```

This pattern lives in `getNextReviewCard` (lastAnsweredCardId), `getDeckInfo`
(time stats), and `getDeckReviewsByDay`. Use it for any new revlog query
scoped to a deck.

### Batch per-deck queries with `GROUP BY did`

If you find yourself writing a per-deck SQL query inside a loop, collapse
it into one query using `c.did IN (?, ?, ...)` + `GROUP BY c.did`, then
build a `{did: stats}` dict and look up per deck. One DB roundtrip beats
N every time, and the win grows with deck count and revlog size.

### Deck enumeration: never iterate `collection.decks.decks.items()`

For "this deck and all descendants", use the cached backend RPCs:

- `collection.decks.deck_and_child_ids(deck_id)` → list of ids (parent + descendants)
- `collection.decks.children(deck_id)` → list of `(name, id)` (descendants only)

Iterating `collection.decks.decks` with `name.startswith(parent + '::')`
is O(total_decks) per call and shows up immediately in users with large
collections.

### Tree walks: index once — iteratively, storing values not nodes

`collection.decks.find_deck_in_tree(tree, deckId)` walks the tree per call.
If you need it in a loop, walk the tree once into a dict and look up O(1) —
but walk it **iteratively** (explicit stack) and store the **plain values**
you need (ints/tuples), never the protobuf nodes. A recursive nested closure
filling a `{did: node}` dict is the exact shape that leaked in `getDeckInfo`
(see the GC rule below).

### Memory: Anki disables the cyclic GC — no per-request reference cycles

Anki calls `gc.disable()` at startup (`aqt/main.py`). Python's cyclic
collector therefore **never runs automatically**, so any reference cycle
created while handling a request is **never freed** — it leaks permanently
and the process grows until the OOM killer takes Anki (and every API
consumer) down. This actually happened: `getDeckInfo` leaked the whole deck
tree on every call until the droplet OOM'd — see `INCIDENT.md`. Plain
refcounted cleanup is fine; **cycles are the trap**, and the leak rate is
`call frequency × retained size`, so polled endpoints are the worst.

- **No self-referencing nested closures.** A nested `def _walk(node): ...;
  _walk(child)` closes over its own name → a function↔cell cycle that retains
  everything it captured. Use an iterative stack/queue and store plain values:
  ```python
  tree_counts = {}
  stack = [collection.sched.deck_due_tree()]
  while stack:
      node = stack.pop()
      tree_counts[int(node.deck_id)] = (node.new_count, node.review_count)  # ints
      stack.extend(node.children)
  ```
- **Don't retain backend objects past the request.** Protobuf nodes from
  `deck_due_tree()`, `get_queued_cards()` results, `Card`/`Note` objects —
  pull out the plain fields you need and let them go; don't stash them in a
  dict/list/closure that can form a cycle.
- If a cycle is truly unavoidable, break it before returning (set refs to
  `None`) or call `gc.collect()` — but prefer not creating one.

**Flag in code review:** any nested `def` that recurses, any `{id: node}`
dict or list holding backend objects, any closure capturing a large structure.

### Modern Anki APIs to prefer (2.1.50+)

- `collection.add_note(note, deck_id)` — runs in a Rust transaction, fires
  `note_will_be_added` + op-framework UI hooks itself. Don't wrap in
  `startEditing/stopEditing`; that triggers the obsolete `aqt.mw.requireReset()`
  which prints a stack trace and forces a full UI reset on every call.
- `collection.add_notes(requests)` — single-transaction batch add.
- `collection._backend.get_queued_cards(...)` — one RPC for next-card +
  scheduling states, replaces `sched.getCard()` + `get_scheduling_states()`.
- `collection._backend.grade_now(...)` — answers any card by id without the
  "top of queue" check (see `answerCard` for the why).
- `collection.autosave()` is a deprecated no-op — saving is automatic.
  Don't add it to new code.

### HTTP downloads: use the module-level `requests.Session`

`utils/helpers.py` exposes `download(url)` backed by a shared
`requests.Session` with a `User-Agent` header. Reuse it instead of opening
fresh `urllib.urlopen` calls — the session pools TCP/TLS connections so
sequential downloads (e.g. audio per note in a batch) skip the handshake.
The default `Python-urllib` UA gets throttled or 403'd by some CDNs.

### Skip redundant writes

`collection.decks.select(did)` persists `current_deck_id` to the config —
guard with `if collection.decks.selected() != did:` for polling endpoints.
Same principle for any setter: check before write if the call site fires
on every poll.

### `includeRendered` / opt-in HTML rendering

`card.question()` / `card.answer()` go through the template renderer
(Tera + cloze + JS/MathJax) and are the dominant CPU cost in card-info
endpoints. When adding new card-returning endpoints, take a `needRender`
(or equivalent) flag defaulting to `False`. Reviewer clients pass `True`;
polling clients get the fast path. See `getNextReviewCard` for the
established pattern.

## graphify

When the user types `/graphify`, invoke the Skill tool with `skill: "graphify"` before doing anything else.
