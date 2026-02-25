# Update Note Fields API

## Overview

The `updateNoteFields` API allows you to edit note fields while **automatically preserving all card timing data** (intervals, ease factors, due dates, review history, etc.). This unified API supports both text field updates and audio downloads from URLs.

## Key Features

✅ **Preserves Card Timing** - All scheduling data remains untouched  
✅ **Unified API** - Handles both text and audio in one call  
✅ **Flexible** - Update text only, audio only, or both  
✅ **Simple** - Requires only noteId  
✅ **Automatic Audio Download** - Downloads and stores audio from URLs  
✅ **Error Handling** - Comprehensive validation and error messages  
✅ **Undo Support** - Creates an undo entry in Anki

## How It Works

### Anki's Data Model

In Anki:

- **Notes** contain the content (fields like "Front", "Back", "Audio")
- **Cards** contain the scheduling data (interval, ease, due date, lapses, etc.)

When you edit a note's fields, the **card timing data is automatically preserved** because they are separate entities in Anki's database.

## API Specification

### Endpoint

```
POST http://localhost:8765
```

### Action

```json
{
  "action": "updateNoteFields",
  "version": 6,
  "params": {
    "note": {
      "id": <noteId>,
      "fields": { ... },      // optional
      "audioFields": { ... }  // optional
    }
  }
}
```

### Parameters

| Parameter     | Type    | Required | Description                               |
| ------------- | ------- | -------- | ----------------------------------------- |
| `id`          | integer | Yes      | Note ID to update                         |
| `fields`      | object  | No       | Text field updates: `{fieldName: value}`  |
| `audioFields` | object  | No       | Audio field URLs: `{fieldName: audioUrl}` |

**Note:** At least one of `fields` or `audioFields` must be provided.

## Usage Examples

### Example 1: Update Text Fields Only

```json
{
  "action": "updateNoteFields",
  "version": 6,
  "params": {
    "note": {
      "id": 1234567890,
      "fields": {
        "Front": "Updated front text",
        "Back": "Updated back text",
        "Extra": "Additional information"
      }
    }
  }
}
```

**Response:**

```json
{
  "result": {
    "noteId": 1234567890,
    "fields": {
      "Front": "Updated front text",
      "Back": "Updated back text",
      "Extra": "Additional information"
    },
    "tags": ["tag1", "tag2"],
    "modelName": "Basic",
    "cards": [1234567891, 1234567892]
  },
  "error": null
}
```

### Example 2: Update Audio Field Only

```json
{
  "action": "updateNoteFields",
  "version": 6,
  "params": {
    "note": {
      "id": 1234567890,
      "audioFields": {
        "Audio": "https://example.com/audio/pronunciation.mp3"
      }
    }
  }
}
```

**Response:**

```json
{
  "result": {
    "noteId": 1234567890,
    "fields": {
      "Front": "existing text",
      "Audio": "[sound:pronunciation_1709123456.mp3]"
    },
    "tags": [],
    "modelName": "Basic",
    "cards": [1234567891]
  },
  "error": null
}
```

### Example 3: Update Both Text and Audio

```json
{
  "action": "updateNoteFields",
  "version": 6,
  "params": {
    "note": {
      "id": 1234567890,
      "fields": {
        "Front": "New vocabulary word",
        "Back": "Definition here"
      },
      "audioFields": {
        "Audio": "https://cdn.example.com/audio/word_pronunciation.mp3"
      }
    }
  }
}
```

**Response:**

```json
{
  "result": {
    "noteId": 1234567890,
    "fields": {
      "Front": "New vocabulary word",
      "Back": "Definition here",
      "Audio": "[sound:word_pronunciation_1709123456.mp3]"
    },
    "tags": ["vocabulary"],
    "modelName": "Basic",
    "cards": [1234567891]
  },
  "error": null
}
```

## Audio Field Behavior

### Audio Download Process

1. **Download** - Audio file is downloaded from the provided URL
2. **Generate Filename** - Unique filename created using timestamp and original name
3. **Store** - Audio file saved to Anki's media folder
4. **Replace Field** - Field content replaced with `[sound:filename.mp3]`

### Audio Filename Format

The API generates unique filenames to avoid conflicts:

- If URL has a filename: `originalname_1709123456.mp3`
- If URL has no filename: `audio_1709123456_abc12345.mp3`

### Important Notes

- **Audio replaces entire field** - The field content is completely replaced with the audio reference
- **Existing audio is overwritten** - If the field had audio before, it will be replaced
- **Multiple formats supported** - MP3, WAV, OGG, and other formats supported by Anki

## Error Handling

### Common Errors

| Error                               | Cause                    | Solution                             |
| ----------------------------------- | ------------------------ | ------------------------------------ |
| "Note ID is required"               | Missing `id` parameter   | Include noteId in request            |
| "Failed to get note with ID X"      | Note doesn't exist       | Verify noteId exists                 |
| "Field 'X' not found in note type"  | Field name doesn't exist | Check field names with `notesInfo`   |
| "No fields or audioFields provided" | Both parameters empty    | Provide at least one field to update |
| "Failed to download audio from URL" | Audio URL unreachable    | Check URL is accessible              |
| "Invalid audio URL for field 'X'"   | URL is empty or invalid  | Provide valid HTTP/HTTPS URL         |

### Example Error Response

```json
{
  "result": null,
  "error": "Field 'InvalidField' not found in note type 'Basic'"
}
```

## Getting Note ID

If you have a cardId but need the noteId, use `cardsInfo`:

```json
{
  "action": "cardsInfo",
  "version": 6,
  "params": {
    "cards": [1234567891]
  }
}
```

Response includes `note` field with the noteId.

## Best Practices

### 1. Verify Field Names

Use `notesInfo` to get the exact field names before updating:

```json
{
  "action": "notesInfo",
  "version": 6,
  "params": {
    "notes": [1234567890]
  }
}
```

### 2. Handle Audio URLs Properly

- Use direct URLs to audio files
- Ensure URLs are accessible from the Anki instance
- Supported formats: MP3, WAV, OGG, FLAC, M4A

### 3. Batch Updates

For multiple notes, make separate API calls. Consider rate limiting to avoid overwhelming Anki.

### 4. Error Recovery

Always check the `error` field in responses and implement proper error handling in your application.

## Comparison with Legacy API

### Before (Old API)

```json
{
  "action": "updateNoteFields",
  "params": {
    "id": 1234567890,
    "fields": { "Front": "text" }
  }
}
// No audio support, used deprecated flush()
```

### After (New Unified API)

```json
{
  "action": "updateNoteFields",
  "params": {
    "note": {
      "id": 1234567890,
      "fields": { "Front": "text" },
      "audioFields": { "Audio": "https://url.com/audio.mp3" }
    }
  }
}
// Supports audio, uses modern col.update_note()
```

### Key Improvements

1. ✅ Audio download support
2. ✅ Modern Anki API (`col.update_note()` vs deprecated `note.flush()`)
3. ✅ Better error messages
4. ✅ Returns updated note info
5. ✅ Creates undo entry
6. ✅ Field validation

## Technical Details

### Card Timing Preservation

The following card data is **automatically preserved**:

- `interval` (ivl) - Time until next review
- `ease factor` (factor) - Card difficulty multiplier
- `due date` (due) - When card is due for review
- `reps` - Number of times reviewed
- `lapses` - Number of times forgotten
- `queue` - Current review queue
- `type` - Card type (new/learning/review)
- Review history (revlog) - Complete history preserved

### Database Operations

1. Fetches note by ID
2. Updates specified fields
3. Calls `collection.update_note(note)` - Modern Anki API
4. Autosaves collection
5. Returns updated note data

**No card data is modified** - only note fields are updated.

## Integration Examples

### JavaScript/Node.js

```javascript
async function updateNoteFields(noteId, textFields, audioFields = {}) {
  const response = await fetch("http://localhost:8765", {
    method: "POST",
    body: JSON.stringify({
      action: "updateNoteFields",
      version: 6,
      params: {
        note: {
          id: noteId,
          fields: textFields,
          audioFields: audioFields,
        },
      },
    }),
  });

  const result = await response.json();
  if (result.error) {
    throw new Error(result.error);
  }
  return result.result;
}

// Usage
await updateNoteFields(
  1234567890,
  { Front: "Hello", Back: "World" },
  { Audio: "https://example.com/audio.mp3" },
);
```

### Python

```python
import requests

def update_note_fields(note_id, text_fields=None, audio_fields=None):
    payload = {
        "action": "updateNoteFields",
        "version": 6,
        "params": {
            "note": {
                "id": note_id,
                "fields": text_fields or {},
                "audioFields": audio_fields or {}
            }
        }
    }

    response = requests.post('http://localhost:8765', json=payload)
    result = response.json()

    if result['error']:
        raise Exception(result['error'])

    return result['result']

# Usage
update_note_fields(
    1234567890,
    text_fields={'Front': 'Hello', 'Back': 'World'},
    audio_fields={'Audio': 'https://example.com/audio.mp3'}
)
```

## Frequently Asked Questions

### Q: Will this reset my card's review schedule?

**A:** No! Card timing data (intervals, ease, due dates) is completely preserved.

### Q: Can I update multiple notes at once?

**A:** No, each API call updates one note. Make multiple calls for multiple notes.

### Q: What happens if the audio download fails?

**A:** The API returns an error and no fields are updated (all-or-nothing transaction).

### Q: Can I update only some fields and leave others unchanged?

**A:** Yes! Only specify the fields you want to update. Other fields remain unchanged.

### Q: Does this work with cloze deletion notes?

**A:** Yes! Works with all note types (Basic, Cloze, custom note types).

### Q: What if a note has multiple cards?

**A:** All cards from the same note will reflect the updated fields. Timing data for each card is preserved independently.

## See Also

- [notesInfo](../README.md#notesinfo) - Get note information
- [cardsInfo](../README.md#cardsinfo) - Get card information
- [addAudioNote](./AUDIO_NOTES.md) - Add new notes with audio
- [updateModel](./NOTE_MANAGEMENT_README.md) - Update note types

## Support

For issues or questions:

1. Check the error message for specific guidance
2. Verify Anki is running with AnkiConnect enabled
3. Test with simple text-only updates first
4. Check network access if audio downloads fail
