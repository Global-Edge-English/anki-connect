# Audio Notes from URL

Add notes to Anki with audio files from external URLs (e.g., Digital Ocean Spaces, S3, or any publicly accessible URL).

## Overview

The `addAudioNote` API endpoint downloads audio files from a URL and stores them in Anki's media folder, making them available offline and allowing them to sync with AnkiWeb.

## API Usage

### Endpoint: `addAudioNote`

Creates a note with audio file from URL.

**Request:**

```json
{
  "action": "addAudioNote",
  "version": 5,
  "params": {
    "note": {
      "deckName": "Vocabulary",
      "modelName": "Basic",
      "fields": {
        "Front": "hello",
        "Back": "a greeting"
      },
      "tags": ["english", "audio"]
    },
    "audioFile": "https://my-space.nyc3.digitaloceanspaces.com/audio/hello.mp3"
  }
}
```

**Parameters:**

- `note`: Standard note parameters
  - `deckName`: Target deck name
  - `modelName`: Note model/type name
  - `fields`: Dictionary of field names and values
  - `tags`: Array of tags (optional)
- `audioFile`: URL to audio file (MP3, WAV, OGG, etc.)
- `allowDuplicate`: Allow duplicate notes (optional, default: `true`)

**Required Note Fields:**

Your note model must have an `Audio1` field. The audio file reference will be automatically added to this field.

**Response:**

```json
{
  "result": 1234567890123,
  "error": null
}
```

Returns the note ID on success.

## How It Works

1. Downloads audio file from provided URL
2. Generates unique filename with timestamp (e.g., `hello_1234567890.mp3`)
3. Saves file to Anki's media folder
4. Adds `[sound:filename.mp3]` reference to `Audio1` field
5. Creates note in specified deck

## Benefits

- ✅ **Offline access** - Audio files stored locally in Anki
- ✅ **AnkiWeb sync** - Files sync properly with AnkiWeb
- ✅ **No API costs** - No external API dependencies
- ✅ **Flexible** - Works with any publicly accessible audio URL
- ✅ **Fast** - Direct file download, no processing time

## Supported Audio Formats

- MP3 (`.mp3`)
- WAV (`.wav`)
- OGG (`.ogg`)
- M4A (`.m4a`)
- FLAC (`.flac`)

## Common Errors

| Error                    | Solution                                           |
| ------------------------ | -------------------------------------------------- |
| Audio1 field required    | Ensure note model has an `Audio1` field            |
| Failed to download audio | Check URL is publicly accessible and valid         |
| Model not found          | Verify model name matches exactly (case-sensitive) |
| Deck not found           | Verify deck name matches exactly (case-sensitive)  |
| Downloaded file is empty | Check URL returns valid audio file                 |

## Examples

### Python

```python
import requests

payload = {
    "action": "addAudioNote",
    "version": 5,
    "params": {
        "note": {
            "deckName": "Spanish",
            "modelName": "Basic",
            "fields": {
                "Front": "hola",
                "Back": "hello"
            },
            "tags": ["spanish", "audio"]
        },
        "audioFile": "https://my-bucket.s3.amazonaws.com/audio/hola.mp3"
    }
}

response = requests.post('http://localhost:8765', json=payload)
result = response.json()

if result['error']:
    print(f"Error: {result['error']}")
else:
    print(f"Note created with ID: {result['result']}")
```

### JavaScript

```javascript
async function addAudioNote(audioUrl, word, translation) {
  const response = await fetch("http://localhost:8765", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      action: "addAudioNote",
      version: 5,
      params: {
        note: {
          deckName: "Vocabulary",
          modelName: "Basic",
          fields: {
            Front: word,
            Back: translation,
          },
          tags: ["audio"],
        },
        audioFile: audioUrl,
      },
    }),
  });

  const result = await response.json();

  if (result.error) {
    console.error("Error:", result.error);
  } else {
    console.log("Note ID:", result.result);
  }
}

// Usage
addAudioNote(
  "https://storage.googleapis.com/my-bucket/bonjour.mp3",
  "bonjour",
  "hello"
);
```

### cURL

```bash
curl -X POST http://localhost:8765 \
  -H "Content-Type: application/json" \
  -d '{
    "action": "addAudioNote",
    "version": 5,
    "params": {
      "note": {
        "deckName": "German",
        "modelName": "Basic",
        "fields": {
          "Front": "guten tag",
          "Back": "good day"
        },
        "tags": ["german"]
      },
      "audioFile": "https://my-cdn.com/audio/guten-tag.mp3"
    }
  }'
```

## URL Sources

The `audioFile` parameter accepts any publicly accessible URL:

- **Digital Ocean Spaces:** `https://my-space.nyc3.digitaloceanspaces.com/audio/file.mp3`
- **AWS S3:** `https://my-bucket.s3.amazonaws.com/audio/file.mp3`
- **Google Cloud Storage:** `https://storage.googleapis.com/my-bucket/file.mp3`
- **Direct URLs:** `https://example.com/path/to/audio.mp3`
- **CDN URLs:** Any CDN-hosted audio file

**Note:** URLs must be publicly accessible. Private/authenticated URLs are not supported.

## Tips

1. **Filename Generation:** Filenames are auto-generated with timestamps to avoid conflicts
2. **Duplicate Notes:** Set `allowDuplicate: false` to prevent duplicate notes
3. **Multiple Fields:** You can populate multiple fields in addition to the audio
4. **Batch Processing:** Use standard `addNotes` if you need to add multiple notes without audio

## Troubleshooting

### URL Returns 404

- Verify the URL is correct and file exists
- Ensure the file is publicly accessible (not behind authentication)
- Check for typos in the URL

### Audio Not Playing in Anki

- Verify the file format is supported
- Check that the file downloaded correctly (check Anki media folder)
- Ensure `Audio1` field is properly configured in your card template

### Network Timeout

- Check your internet connection
- Verify the server hosting the audio is responding
- Consider hosting audio on a faster CDN
