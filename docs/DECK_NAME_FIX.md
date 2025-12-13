# Fix: Notes Being Added to Default Deck Instead of Specified Deck

## Problem

The `addNote` and `addAudioNote` methods were sometimes adding notes to the default deck instead of the deck specified in the `deckName` parameter. This was particularly noticeable with nested decks like `"staging_c1db9e68-e1c7-418d-a6f0-2bf6f8911957::Text"`.

## Root Cause

The issue had two components:

### 1. Using Deprecated Anki API

The code was calling the deprecated `collection.addNote(note)` method, which:

- Does NOT take a deck parameter
- Creates notes in the **notetype's default deck** (stored in `note.note_type()["did"]`)
- Completely ignores the `deckName` parameter provided in the API request

### 2. Unreliable Card Movement Logic

After creating the note, the code attempted to move cards to the correct deck:

```python
if cardIds and deck['id'] != collection.decks.get_current_id():
    self.changeDeck(cardIds, params.deckName)
```

This conditional check would **fail to move cards** when:

- The target deck ID happened to match the currently selected deck in the Anki UI
- But the note was actually created in a different deck (the notetype's default)

## Solution

### Use Modern Anki API

Updated both methods to use the modern `collection.add_note(note, deck_id)` API which:

- Takes an explicit `deck_id` parameter
- Creates the note directly in the specified deck
- Available in Anki 2.1.50+

### Backward Compatibility

The fix includes a fallback for older Anki versions:

```python
try:
    # Try modern add_note() API (Anki 2.1.50+)
    collection.add_note(note, deck['id'])
except (AttributeError, TypeError):
    # Fall back to deprecated addNote() for older Anki versions
    collection.addNote(note)
    # Move cards to correct deck (removes unreliable conditional)
    cardIds = [card.id for card in note.cards()]
    if cardIds:
        self.changeDeck(cardIds, params.deckName)
```

### Key Changes

1. **Primary approach**: Use `collection.add_note(note, deck['id'])` with explicit deck ID
2. **Remove conditional check**: In fallback mode, always move cards if any exist
3. **Maintain compatibility**: Gracefully handle both modern and legacy Anki versions

## Affected Methods

- `AnkiBridge.addNote()` - Main note creation method
- `AnkiBridge.addAudioNote()` - Audio note creation method

## Testing

To verify the fix works:

1. **Test with nested decks**:

```json
{
  "action": "addNote",
  "version": 6,
  "params": {
    "note": {
      "deckName": "Parent::Child::Grandchild",
      "modelName": "Basic",
      "fields": {
        "Front": "Test Question",
        "Back": "Test Answer"
      }
    }
  }
}
```

2. **Test with multi action**:

```json
{
  "action": "multi",
  "version": 5,
  "params": {
    "actions": [
      {
        "action": "addNote",
        "params": {
          "note": {
            "deckName": "staging_c1db9e68-e1c7-418d-a6f0-2bf6f8911957::Text",
            "modelName": "Studypoint",
            "fields": {
              "Studypoint": "test",
              "Example Sentence": "We have a big test tomorrow in science class.",
              "Translation": "We have a big test tomorrow in science class.",
              "Definition": "a method of assessing someone's knowledge or abilities",
              "Part of Speech": "noun"
            }
          }
        }
      }
    ]
  }
}
```

3. **Verify deck placement**: After adding notes, check in Anki that the cards appear in the specified deck, not the default deck.

## Benefits

1. **Reliability**: Notes are now always created in the correct deck
2. **Consistency**: Behavior is predictable regardless of:
   - Notetype default deck settings
   - Currently selected deck in Anki UI
   - Deck hierarchy complexity
3. **Modern API**: Uses the recommended Anki API for note creation
4. **Backward Compatible**: Still works with older Anki versions

## References

- Anki source: `/Users/vasundhara/anki/pylib/anki/collection.py`
- Modern API: `Collection.add_note(note: Note, deck_id: DeckId)`
- Deprecated API: `Collection.addNote(note: Note)`
