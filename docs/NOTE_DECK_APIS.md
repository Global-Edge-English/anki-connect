# Note & Deck APIs: getNoteIds, deleteNote, undoAnswerCard

## Overview

Three new API endpoints for paginated note retrieval, note deletion, and undoing a card answer.

---

## `getNoteIds`

Get a paginated list of note IDs using an optional deck name and/or a free-text search query — the same syntax as Anki's card browser. At least one of `deckName` or `query` must be provided.

### Parameters

| Parameter  | Type   | Required | Default | Description                                                                    |
| ---------- | ------ | -------- | ------- | ------------------------------------------------------------------------------ |
| `deckName` | string | ❌ No    | —       | Parent deck name. Subdecks are automatically included. Required if no `query`. |
| `page`     | int    | ❌ No    | `1`     | 1-indexed page number                                                          |
| `pageSize` | int    | ❌ No    | `50`    | Number of note IDs per page                                                    |
| `query`    | string | ❌ No    | —       | Anki search query (same syntax as card browser). Required if no `deckName`.    |

**Notes:**

- At least one of `deckName` or `query` must be provided
- When both are given, they are combined with AND: `deck:"MyDeck" tag:important`
- `query` supports the full Anki search syntax: `tag:`, `is:due`, `is:new`, `flag:`, `added:7`, `rated:3`, field content searches, etc.
- Note IDs are returned in the order Anki's `find_notes` returns them (generally by note creation time)
- The response includes a `query` field showing the exact query that was executed

### Sample Requests

**By deck name only (all notes in deck + subdecks):**

```json
{
  "action": "getNoteIds",
  "version": 5,
  "params": {
    "deckName": "MyParentDeck",
    "page": 1,
    "pageSize": 50
  }
}
```

**By deck name + search filter:**

```json
{
  "action": "getNoteIds",
  "version": 5,
  "params": {
    "deckName": "MyParentDeck",
    "query": "tag:difficult is:due",
    "page": 1,
    "pageSize": 50
  }
}
```

**Search across all decks (no deckName):**

```json
{
  "action": "getNoteIds",
  "version": 5,
  "params": {
    "query": "flag:1 added:7",
    "page": 1,
    "pageSize": 20
  }
}
```

### Sample Response

```json
{
  "result": {
    "noteIds": [1234567890, 1234567891, 1234567892],
    "page": 1,
    "pageSize": 50,
    "total": 342,
    "totalPages": 7,
    "query": "deck:\"MyParentDeck\" tag:difficult is:due"
  },
  "error": null
}
```

### Useful Query Examples

| Goal                                     | `query` value |
| ---------------------------------------- | ------------- |
| Notes with a specific tag                | `tag:grammar` |
| Notes added in last 7 days               | `added:7`     |
| Notes with due cards                     | `is:due`      |
| Notes with new cards                     | `is:new`      |
| Notes on flagged cards                   | `flag:1`      |
| Notes rated Again in last 3 days         | `rated:3:1`   |
| Notes where Front field contains "hello" | `Front:hello` |
| Notes NOT in a tag                       | `-tag:easy`   |

### Error Cases

- `"At least one of 'deckName' or 'query' must be provided"` — both were omitted
- `"Deck 'X' does not exist"` — the specified deck name was not found
- `"Invalid search query '...': ..."` — Anki rejected the query syntax
- `"page must be >= 1"` — invalid page number
- `"pageSize must be >= 1"` — invalid page size

### Usage Example (Fetch All Notes in Batches)

```python
page = 1
all_note_ids = []
while True:
    result = anki_connect("getNoteIds", {"deckName": "MyDeck", "page": page, "pageSize": 100})
    all_note_ids.extend(result["noteIds"])
    if page >= result["totalPages"]:
        break
    page += 1
```

---

## `deleteNote`

Delete a note and all its associated cards by note ID.

### Parameters

| Parameter | Type | Required | Description              |
| --------- | ---- | -------- | ------------------------ |
| `noteId`  | int  | ✅ Yes   | ID of the note to delete |

**Notes:**

- Deletes **all cards** belonging to the note as well
- This operation is **irreversible** — there is no built-in undo for note deletion
- Uses the modern `collection.remove_notes()` API with fallback to `collection.remNotes()` for older Anki versions

### Sample Request

```json
{
  "action": "deleteNote",
  "version": 5,
  "params": {
    "noteId": 1234567890
  }
}
```

### Sample Response

```json
{
  "result": true,
  "error": null
}
```

### Error Cases

- `"Note with ID '...' does not exist"` — the note ID was not found in the collection
- `"noteId is required"` — noteId was null or missing

---

## `undoAnswerCard`

Undo the most recent answer for a specific card. This is a **per-card undo** — it targets a specific card by ID and undoes its latest review, regardless of what other cards have been answered since.

### How It Works

1. Finds the most recent entry in the `revlog` table for the given `cardId`
2. Reads the pre-answer state (`lastIvl` = interval before the answer, prior `factor`)
3. **Deletes** that revlog entry from the database
4. **Restores** the card's scheduling state to what it was before the answer

After calling this API, the card is immediately available in the review queue again.

### Parameters

| Parameter | Type | Required | Description                                |
| --------- | ---- | -------- | ------------------------------------------ |
| `cardId`  | int  | ✅ Yes   | ID of the card whose latest answer to undo |

### Sample Request

```json
{
  "action": "undoAnswerCard",
  "version": 5,
  "params": {
    "cardId": 1234567890
  }
}
```

### Sample Response

```json
{
  "result": {
    "cardId": 1234567890,
    "restoredState": "review",
    "restoredInterval": 14
  },
  "error": null
}
```

### Response Fields

| Field              | Type   | Description                                                                                            |
| ------------------ | ------ | ------------------------------------------------------------------------------------------------------ |
| `cardId`           | int    | The card ID that was undone                                                                            |
| `restoredState`    | string | `"new"`, `"learning"`, or `"review"` — the state before the answer                                     |
| `restoredInterval` | int    | The card's interval before the answer (`0` = new, negative = learning seconds, positive = review days) |

### State Restoration Logic

| `lastIvl` value | Meaning before the answer | Restored to                                    |
| --------------- | ------------------------- | ---------------------------------------------- |
| `0`             | Card was new              | New queue (`queue=0`), due by ordinal position |
| `< 0`           | Card was in learning step | Learning queue (`queue=1`), due immediately    |
| `> 0`           | Card was a mature review  | Review queue (`queue=2`), due today            |

### Queue Availability After Undo

| Restored State | When card appears next                  |
| -------------- | --------------------------------------- |
| `new`          | When new cards are served from the deck |
| `learning`     | Immediately (learning queue, due = now) |
| `review`       | Immediately (due today)                 |

### Error Cases

- `"Card with ID '...' does not exist"` — card not found
- `"No answer history found for card '...'"` — card has never been answered (no revlog entries)
- `"cardId is required"` — missing cardId

### Important Notes

- This is **not** the same as Anki's built-in Ctrl+Z undo — it targets a specific card's last answer regardless of review order
- The revlog entry is **permanently deleted** — this cannot itself be undone
- Anki's in-memory session counters (shown in the UI) won't auto-update until the next scheduler refresh, but the card is fully available via the API immediately
- If the same card has been answered multiple times, only the **most recent** answer is undone per call; call again to undo earlier answers

---

## Common Workflow: Review → Undo → Re-review

```javascript
// 1. Get next card
const card = await ankiConnect("getNextReviewCard", { deckName: "MyDeck" });

// 2. Answer it
await ankiConnect("answerCard", { cardId: card.cardId, ease: 1 });

// 3. Oops, wrong answer — undo it
const undoResult = await ankiConnect("undoAnswerCard", { cardId: card.cardId });
// undoResult.restoredState === "review"
// undoResult.restoredInterval === 14

// 4. Card is immediately available again — answer correctly
const sameCard = await ankiConnect("getNextReviewCard", { deckName: "MyDeck" });
await ankiConnect("answerCard", { cardId: sameCard.cardId, ease: 3 });
```
