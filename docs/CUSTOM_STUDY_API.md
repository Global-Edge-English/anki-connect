# Custom Study APIs

This document describes the custom study APIs available in AnkiConnect for customizing deck study settings.

## Overview

These APIs allow you to:

1. **Set daily card limits** (convenience wrapper for getDeckConfig/saveDeckConfig)
2. **Extend today's new card limit** (truly new feature)
3. **Create filtered decks for forgotten cards** (truly new feature)
4. **Combine multiple operations** (truly new feature)

## API Reference

### 1. setDeckStudyOptions

A convenience wrapper for easily changing daily card limits **for a specific deck only**. If the deck is using a shared configuration, this API will automatically clone the configuration to ensure only the specified deck is affected.

**Endpoint:** `setDeckStudyOptions`

**Parameters:**

- `deckName` (string, required): Name of the deck to configure
- `newCardsPerDay` (integer, optional): Maximum new cards to study per day
- `reviewsPerDay` (integer, optional): Maximum review cards per day

**Returns:** Object with updated configuration

**Example Request:**

```json
{
  "action": "setDeckStudyOptions",
  "version": 5,
  "params": {
    "deckName": "Japanese Vocabulary",
    "newCardsPerDay": 30,
    "reviewsPerDay": 200
  }
}
```

**Example Response:**

```json
{
  "result": {
    "deckName": "Japanese Vocabulary",
    "configId": 1502972374573,
    "configName": "Japanese Vocabulary Options",
    "newCardsPerDay": 30,
    "reviewsPerDay": 200,
    "wasShared": true,
    "createdNewConfig": true
  },
  "error": null
}
```

**Important:**

- If the deck is using a shared configuration (e.g., "Default"), a new deck-specific configuration will be automatically created (e.g., "Japanese Vocabulary Options")
- This ensures that changing settings for one deck does NOT affect other decks
- The response includes `wasShared` and `createdNewConfig` flags to indicate if a new config was created

---

### 2. extendNewCardLimit

Extends today's new card limit for a specific deck using Anki's built-in custom study mechanism. This is **temporary** and only affects today - tomorrow the limit resets automatically.

**Endpoint:** `extendNewCardLimit`

**Parameters:**

- `deckName` (string, required): Name of the deck
- `additionalCards` (integer, required): Number of additional new cards to allow today

**Returns:** Object with extension information

**Example Request:**

```json
{
  "action": "extendNewCardLimit",
  "version": 5,
  "params": {
    "deckName": "Japanese Vocabulary",
    "additionalCards": 20
  }
}
```

**Example Response:**

```json
{
  "result": {
    "deckName": "Japanese Vocabulary",
    "additionalCardsAllowed": 20,
    "totalExtended": 20,
    "message": "Extended new card limit by 20 cards for today"
  },
  "error": null
}
```

**Use Case:** You've finished your daily 20 new cards but want to study 20 more today.

**Important:**

- Uses Anki's `extend_limits()` method - the same mechanism as the custom study dialog
- This is **temporary** - only affects TODAY's limit
- Tomorrow the limit automatically resets to your configured perDay value
- No manual reset needed!

---

### 3. enableStudyForgotten

Creates a filtered deck containing cards that you answered "Again" (forgot) in the last X days. Matches Anki's native "Review forgotten cards" custom study option - **includes ALL forgotten cards with no limit**.

**Endpoint:** `enableStudyForgotten`

**Parameters:**

- `deckName` (string, required): Name of the source deck
- `days` (integer, optional): Look back this many days for forgotten cards (default: 1 = today only)
- `filteredDeckName` (string, optional): Custom name for the filtered deck. If not provided, auto-generates name.

**Returns:** Object with filtered deck information

**Example Request (with custom name):**

```json
{
  "action": "enableStudyForgotten",
  "version": 5,
  "params": {
    "deckName": "Japanese Vocabulary",
    "days": 3,
    "filteredDeckName": "My Custom Review Deck"
  }
}
```

**Example Request (auto-generated name):**

```json
{
  "action": "enableStudyForgotten",
  "version": 5,
  "params": {
    "deckName": "Japanese Vocabulary",
    "days": 3
  }
}
```

**Example Response:**

```json
{
  "result": {
    "sourceDeck": "Japanese Vocabulary",
    "filteredDeckName": "My Custom Review Deck",
    "filteredDeckId": 1234567890123,
    "days": 3,
    "cardsFound": 15,
    "message": "Created filtered deck with 15 forgotten cards from last 3 day(s)"
  },
  "error": null
}
```

**Notes:**

- If `filteredDeckName` is not provided, the deck will be auto-named:
  - `[DeckName] - Forgotten Today` for 1 day
  - `[DeckName] - Forgotten (Last X Days)` for more days
- If a deck with the same name already exists and is a filtered deck, it will be rebuilt with fresh cards
- **Includes ALL matching cards** - no limit (matches Anki's native behavior)

---

### 4. createCustomStudy

A combined API that allows you to perform multiple custom study operations in a single request.

**Endpoint:** `createCustomStudy`

**Parameters:**

- `deckName` (string, required): Name of the deck to configure
- `newCardsPerDay` (integer, optional): Set new cards per day limit
- `reviewsPerDay` (integer, optional): Set reviews per day limit
- `studyForgottenToday` (boolean, optional): Create filtered deck for forgotten cards (default: false)
- `extendNewLimit` (integer, optional): Extend today's new card limit by this many cards

**Returns:** Object with results of all operations

**Example Request:**

```json
{
  "action": "createCustomStudy",
  "version": 5,
  "params": {
    "deckName": "Japanese Vocabulary",
    "newCardsPerDay": 25,
    "extendNewLimit": 10,
    "studyForgottenToday": true
  }
}
```

**Example Response:**

```json
{
  "result": {
    "deckName": "Japanese Vocabulary",
    "operations": {
      "studyOptions": {
        "success": true,
        "data": {
          "deckName": "Japanese Vocabulary",
          "configId": 1,
          "configName": "Default",
          "newCardsPerDay": 25,
          "reviewsPerDay": 100
        }
      },
      "extendNewLimit": {
        "success": true,
        "data": {
          "deckName": "Japanese Vocabulary",
          "additionalCardsAllowed": 10,
          "message": "Extended new card limit by 10 cards for today"
        }
      },
      "studyForgotten": {
        "success": true,
        "data": {
          "sourceDeck": "Japanese Vocabulary",
          "filteredDeckName": "Japanese Vocabulary - Forgotten Today",
          "filteredDeckId": 1234567890123,
          "cardsFound": 8,
          "message": "Created filtered deck with 8 forgotten cards from today"
        }
      }
    }
  },
  "error": null
}
```

**Benefits:**

- Single API call for multiple operations
- Each operation's success/failure is tracked independently
- If one operation fails, others can still succeed

---

## Comparison with Existing APIs

### getDeckConfig / saveDeckConfig (Existing)

These APIs allow full control over deck configuration but require:

1. Fetching the entire config object with `getDeckConfig`
2. Modifying the nested properties (`config.new.perDay`, `config.rev.perDay`)
3. Saving the entire config back with `saveDeckConfig`

**Example with existing APIs:**

```json
// Step 1: Get config
{
    "action": "getDeckConfig",
    "version": 5,
    "params": {
        "deck": "Japanese Vocabulary"
    }
}

// Step 2: Modify the response (in your code)
// config.new.perDay = 30
// config.rev.perDay = 200

// Step 3: Save back
{
    "action": "saveDeckConfig",
    "version": 5,
    "params": {
        "config": { /* entire modified config object */ }
    }
}
```

### setDeckStudyOptions (New - Convenience Wrapper)

Simplifies the above process:

```json
{
  "action": "setDeckStudyOptions",
  "version": 5,
  "params": {
    "deckName": "Japanese Vocabulary",
    "newCardsPerDay": 30,
    "reviewsPerDay": 200
  }
}
```

---

## Use Cases

### 1. Intensive Study Session

You want to do an intensive study session today:

```json
{
  "action": "createCustomStudy",
  "version": 5,
  "params": {
    "deckName": "Japanese Vocabulary",
    "extendNewLimit": 30,
    "studyForgottenToday": true
  }
}
```

### 2. Increase Permanent Daily Limit

You want to permanently increase your daily card limits:

```json
{
  "action": "setDeckStudyOptions",
  "version": 5,
  "params": {
    "deckName": "Japanese Vocabulary",
    "newCardsPerDay": 50,
    "reviewsPerDay": 300
  }
}
```

### 3. Review Difficult Cards

You want to review cards you got wrong in the last 3 days:

```json
{
  "action": "enableStudyForgotten",
  "version": 5,
  "params": {
    "deckName": "Japanese Vocabulary",
    "days": 3
  }
}
```

---

## Error Handling

All APIs return errors in the standard AnkiConnect format:

```json
{
  "result": null,
  "error": "Deck 'NonExistent' does not exist"
}
```

Common errors:

- `"Deck '[name]' does not exist"` - The specified deck was not found
- `"Collection not available"` - Anki is not running or collection is not loaded
- `"newCardsPerDay must be >= 0"` - Invalid parameter value
- `"additionalCards must be > 0"` - Invalid parameter value

---

## Deck Deletion APIs

### deleteDeck

Delete a single deck by name.

**Endpoint:** `deleteDeck`

**Parameters:**

- `deckName` (string, required): Name of the deck to delete
- `deleteCards` (boolean, optional): Whether to delete the cards in the deck as well (default: false)

**Returns:** Boolean indicating success

**Example Request (for filtered/custom study decks):**

```json
{
  "action": "deleteDeck",
  "version": 5,
  "params": {
    "deckName": "My Custom Review Deck",
    "t
  }
}
```

**Example Response:**

```json
{
  "result": true,
  "error": null
}
```

**Important Notes:**

- **For filtered decks (created by `enableStudyForgotten`):** ALWAYS use `deleteCards: false`
  - Filtered decks contain references to cards, not the actual cards
  - The actual cards remain in their source decks
  - `deleteCards: false` removes the filtered deck but keeps cards in source decks
  - `deleteCards: true` would permanently delete the actual cards from Anki ⚠️
- **For regular decks:**
  - `deleteCards: false` moves cards to the default deck
  - `deleteCards: true` permanently deletes all cards in the deck

---

### deleteDecks

Delete multiple decks at once.

**Endpoint:** `deleteDecks`

**Parameters:**

- `decks` (array of strings, required): Names of the decks to delete
- `cardsToo` (boolean, optional): Whether to delete the cards in the decks as well (default: false)

**Returns:** Null on success

**Example Request:**

```json
{
  "action": "deleteDecks",
  "version": 5,
  "params": {
    "decks": ["Filtered Deck 1", "Filtered Deck 2"],
    "cardsToo": false
  }
}
```

**Example Response:**

```json
{
  "result": null,
  "error": null
}
```

---

## Notes

1. **extendNewCardLimit** only affects TODAY's limit. Tomorrow it will reset to the configured daily limit.
2. **enableStudyForgotten** creates a filtered deck that won't reschedule cards (preserves their original scheduling).
3. **setDeckStudyOptions** modifies the deck's configuration group, which may affect other decks using the same configuration.
4. All operations require Anki to be running with AnkiConnect enabled.
5. Use **deleteDeck** or **deleteDecks** to clean up filtered decks when you're done reviewing.
