#!/usr/bin/env python3
"""
anki_leak_probe_all.py — read-only per-endpoint memory-leak bisect for AnkiConnect.

PHASE 1 (this script): hammer every READ-ONLY AnkiConnect action that
studyplan2021 actually uses, N times each, over one keep-alive connection, and
report the cgroup `anon` delta per endpoint (worst first). Write endpoints are
handled separately (see "WRITES" note at the bottom) — this script never mutates.

Why: Anki runs gc.disable() at startup (aqt/main.py), so any per-request
reference cycle created in a handler is never collected and leaks permanently.
The original /usr/local/bin/anki_leak_probe.sh only covered version,
getNextReviewCard and getDeckInfo — so a leak in heatmap (getDeckReviewsByDayMulti),
decknotes (getNoteIds/notesInfo) or the multi() wrapper would have been missed.

STAGING-ONLY: studyplan decks are named "<envName>_<userId>" (staging_*,
production_*, ge-english_*) and ALL three envs share this one AnkiConnect
collection. This probe only ever sends deck names beginning with --env-prefix
(default "staging_") and refuses to run if it can't find any — so it can never
touch production or ge-english data. (Read-only anyway, but belt and suspenders.)

studyplan2021 read-only actions covered:
    version, modelNamesAndIds, getDeckInfo, getNextReviewCard,
    getDeckReviewsByDayMulti, getNoteIds, notesInfo, multi([getcard shape])

Run ON the Anki droplet (it reads the anki.service cgroup):
    python3 anki_leak_probe_all.py                     # N=3000/endpoint
    python3 anki_leak_probe_all.py --n 1000
    python3 anki_leak_probe_all.py --only getDeckInfo,getNextReviewCard
    python3 anki_leak_probe_all.py --deck staging_<uid>   # pin the primary deck

Interpreting output: clean endpoints sit inside the noise band (|Δ| <
--threshold, default 20 MB / N). Anything well above is the leak — chase it as a
per-request reference cycle under gc.disable() (see INCIDENT.md).
"""

import argparse
import http.client
import json
import sys
import time

CGROUP_MEMSTAT = "/sys/fs/cgroup/system.slice/anki.service/memory.stat"

# Read-only by construction. This script must NEVER send anything else.
READ_ONLY_ACTIONS = {
    "version", "modelNamesAndIds", "getDeckInfo", "getNextReviewCard",
    "getDeckReviewsByDayMulti", "getNoteIds", "notesInfo", "deckNamesAndIds",
    "findCards", "findNotes", "multi",
}


def read_anon():
    """Current cgroup anonymous RSS in bytes (the number that climbs on a leak)."""
    try:
        with open(CGROUP_MEMSTAT) as f:
            for line in f:
                if line.startswith("anon "):
                    return int(line.split()[1])
    except FileNotFoundError:
        return None
    return None


class Client:
    """Single keep-alive HTTP connection to AnkiConnect; reconnects on drop."""

    def __init__(self, host, port):
        self.host, self.port = host, port
        self.conn = http.client.HTTPConnection(host, port, timeout=30)

    def call(self, action, params=None, version=6):
        if action not in READ_ONLY_ACTIONS:
            raise RuntimeError(f"refusing non-read-only action: {action}")
        body = json.dumps({"action": action, "version": version,
                           "params": params or {}})
        for attempt in (1, 2):
            try:
                self.conn.request("POST", "/", body,
                                  {"Content-Type": "application/json"})
                data = self.conn.getresponse().read()
                try:
                    return json.loads(data)
                except ValueError:
                    return {"result": None, "error": "non-json response"}
            except (http.client.HTTPException, ConnectionError, OSError):
                try:
                    self.conn.close()
                except Exception:
                    pass
                self.conn = http.client.HTTPConnection(self.host, self.port,
                                                       timeout=30)
                if attempt == 2:
                    return {"result": None, "error": "connection failed"}


def result_of(reply):
    return reply.get("result") if isinstance(reply, dict) else reply


def discover(client, env_prefix, deck_override, multi_count):
    """Find staging parent decks (and note ids) to drive the read-only probes.

    A 'parent' staging deck is one named '<prefix><id>' with no '::' — these are
    the per-user decks studyplan hits; the ones with ::Text/::Audio children
    exercise getDeckInfo's per-child path."""
    names = result_of(client.call("deckNamesAndIds")) or {}
    names = list(names.keys()) if isinstance(names, dict) else []

    staging = [n for n in names if n.startswith(env_prefix)]
    if not staging:
        sys.exit(f"FATAL: no decks matching '{env_prefix}*' — refusing to run so "
                 f"we can't accidentally hit production/ge-english decks.")

    parents = sorted({n for n in staging if "::" not in n
                      and "leakprobe" not in n})
    has_children = [p for p in parents
                    if any(o.startswith(p + "::") for o in staging)]
    pool = has_children or parents

    primary = deck_override or (pool[0] if pool else staging[0])
    if not primary.startswith(env_prefix):
        sys.exit(f"FATAL: --deck {primary!r} is not a {env_prefix}* deck.")

    multi_decks = pool[:multi_count] if pool else [primary]

    note_ids = result_of(client.call("getNoteIds",
                                     {"deckName": primary, "page": 1,
                                      "pageSize": 50, "query": ""}))
    if isinstance(note_ids, dict):
        note_ids = note_ids.get("noteIds", [])
    note_ids = [int(n) for n in (note_ids or [])[:25]]
    return primary, multi_decks, note_ids


def build_probes(primary, multi_decks, note_ids, include_render):
    """(label, action, params) for every read-only studyplan2021 endpoint."""
    getcard_actions = [
        {"action": "getNextReviewCard", "params": {"deckName": primary}},
        {"action": "getDeckInfo",
         "params": {"deckName": primary, "period": "allTime"}},
    ]
    probes = [
        ("version (control)",            "version",                 {}),
        ("modelNamesAndIds",            "modelNamesAndIds",         {}),
        ("getDeckInfo (getowndeckstats)", "getDeckInfo",            {"deckName": primary, "period": "allTime"}),
        ("getDeckInfo single (getcard)", "getDeckInfo",             {"deckName": primary, "period": "allTime", "wantSingleDeckStats": True}),
        ("getNextReviewCard (getcard)", "getNextReviewCard",        {"deckName": primary}),
        ("multi[getcard shape]",        "multi",                    {"actions": getcard_actions}),
        ("getDeckReviewsByDayMulti (heatmap)", "getDeckReviewsByDayMulti", {"deckNames": multi_decks, "days": 14}),
        ("getNoteIds (decknotes)",      "getNoteIds",               {"deckName": primary, "page": 1, "pageSize": 50, "query": ""}),
    ]
    if include_render:
        probes.append(("getNextReviewCard render", "getNextReviewCard",
                       {"deckName": primary, "needRender": True}))
    if note_ids:
        probes.append(("notesInfo (decknotes/flagged)", "notesInfo",
                       {"notes": note_ids}))
    return probes


def run_probe(client, label, action, params, n, settle, threshold):
    """Hammer one endpoint N times, refreshing a live progress line (count,
    rate, and running Δanon so you can watch a leaker climb in real time).
    Owns its own output line; returns (delta_bytes, error)."""
    first = client.call(action, params)
    err = first.get("error") if isinstance(first, dict) else None
    before = read_anon()
    t0 = time.time()
    next_report = t0 + 0.5
    for i in range(1, n + 1):
        client.call(action, params)
        now = time.time()
        if now >= next_report:
            cur = read_anon()
            d = (cur - before) / (1024 * 1024) if (cur is not None and before is not None) else float("nan")
            rate = i / (now - t0) if now > t0 else 0
            sys.stdout.write(f"\r  {label:34s} {i:>5}/{n}  {rate:5.0f}/s  Δ{d:+7.1f}MB   ")
            sys.stdout.flush()
            next_report = now + 0.5
    time.sleep(settle)
    after = read_anon()
    delta = (after - before) if (before is not None and after is not None) else None
    elapsed = time.time() - t0
    if delta is None:
        line = f"\r  {label:34s} {n}/{n}  done in {elapsed:4.0f}s   n/a (no cgroup)"
    else:
        mb = delta / (1024 * 1024)
        tag = "  <-- LEAK" if mb > threshold else ""
        errtag = f"  [error: {err}]" if err else ""
        line = f"\r  {label:34s} {n}/{n}  {elapsed:4.0f}s   {mb:+8.1f} MB{tag}{errtag}"
    # pad to clear any leftover progress chars, then newline
    print(line + " " * 8, flush=True)
    return delta, err


def main():
    ap = argparse.ArgumentParser(description="AnkiConnect read-only leak probe (studyplan2021 endpoints, staging-scoped)")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--n", type=int, default=3000, help="calls per endpoint")
    ap.add_argument("--env-prefix", default="staging_", help="only send decks with this prefix")
    ap.add_argument("--deck", default=None, help="pin the primary staging deck")
    ap.add_argument("--multi-decks", type=int, default=30, help="how many staging decks to fan out in the heatmap probe")
    ap.add_argument("--threshold", type=float, default=20.0, help="MB over which an endpoint is flagged LEAK")
    ap.add_argument("--settle", type=float, default=0.5, help="seconds to wait after a burst before reading anon")
    ap.add_argument("--only", default=None, help="comma-separated action/label substrings to limit the run")
    ap.add_argument("--include-render", action="store_true", help="also probe getNextReviewCard with needRender=True")
    args = ap.parse_args()

    client = Client(args.host, args.port)
    ver = result_of(client.call("version"))
    if read_anon() is None:
        print(f"WARN: cannot read {CGROUP_MEMSTAT} — run this ON the droplet with "
              f"cgroup access; deltas will be blank.", file=sys.stderr)
    print(f"AnkiConnect apiVersion={ver}", flush=True)

    primary, multi_decks, note_ids = discover(client, args.env_prefix, args.deck, args.multi_decks)
    print(f"env-prefix={args.env_prefix!r}  primary={primary!r}  "
          f"heatmap-batch={len(multi_decks)} decks  notes={len(note_ids)}  "
          f"N={args.n}/endpoint  threshold={args.threshold}MB\n", flush=True)

    probes = build_probes(primary, multi_decks, note_ids, args.include_render)
    if args.only:
        want = [s.strip() for s in args.only.split(",")]
        probes = [p for p in probes if any(w in p[0] or w == p[1] for w in want)]

    results = []
    for label, action, params in probes:
        delta, err = run_probe(client, label, action, params, args.n, args.settle, args.threshold)
        results.append((label, delta, err))

    print("\n=== summary (worst first) ===", flush=True)
    for label, delta, err in sorted(results, key=lambda r: (r[1] if r[1] is not None else float("-inf")), reverse=True):
        if delta is None:
            print(f"  {label:34s}   n/a")
            continue
        mb = delta / (1024 * 1024)
        print(f"  {label:34s} {mb:+8.1f} MB{'  LEAK' if mb > args.threshold else ''}"
              f"{f'   [error: {err}]' if err else ''}")

    print("\nNEXT: write endpoints (answerCard, flag/unflag, addNote/deleteNote, "
          "updateNoteFields, createDeck/Model, enableStudyForgotten, extendNewCardLimit, "
          "importPackage) are NOT covered here — discuss the staging-safe approach first.")


if __name__ == "__main__":
    main()
