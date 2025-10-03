# Audio Note Generation with ElevenLabs TTS

Generate audio notes automatically using ElevenLabs Text-to-Speech API.

## Setup

1. Get your API key from [ElevenLabs](https://elevenlabs.io)
2. In Anki: **Tools → AnkiConnect Settings**
3. Enter API key and save

## API Usage

### Endpoint: `addAudioNote`

Creates a note with TTS-generated audio.

**Request:**

```json
{
  "action": "addAudioNote",
  "version": 5,
  "params": {
    "note": {
      "deckName": "My Deck",
      "modelName": "Basic",
      "fields": {
        "Audio": "Text to convert to speech",
        "Front": "Question"
      },
      "tags": ["audio"]
    },
    "language": "en",
    "gender": "random"
  }
}
```

**Parameters:**

- `language` (optional): Language code - "en", "es", "fr", "de", "ja", etc. Default: "en"
- `gender` (optional): "male", "female", or "random". Default: "random"

**Required Note Fields:**

- `Audio`: Text to convert to speech
- `Audio1`: Automatically populated with audio file reference

**Response:**

```json
{
  "result": 1234567890123,
  "error": null
}
```

## How It Works

1. Text from "Audio" field → ElevenLabs API
2. Generated MP3 saved to Anki media folder
3. "Audio" field keeps original text
4. "Audio1" field gets `[sound:filename.mp3]` reference
5. Note created in specified deck

## Voice Configuration

**Default voices** (randomized within gender):

**Male:** Adam, Callum, Daniel  
**Female:** Bella, Freya, Lily

**To customize:** Edit `MALE_VOICES` and `FEMALE_VOICES` lists in `audio_generator.py`

## Common Errors

| Error                | Solution                                          |
| -------------------- | ------------------------------------------------- |
| API key not set      | Configure in Tools → AnkiConnect Settings         |
| Audio field required | Ensure note model has "Audio" and "Audio1" fields |
| Failed to generate   | Check API key, credits, and internet connection   |

## Examples

**Python:**

```python
import requests

payload = {
    "action": "addAudioNote",
    "version": 5,
    "params": {
        "note": {
            "deckName": "Spanish",
            "modelName": "Basic",
            "fields": {"Audio": "Hola", "Front": "Hello"},
            "tags": ["audio"]
        },
        "language": "es",
        "gender": "female"
    }
}

response = requests.post('http://localhost:8765', json=payload)
print(response.json())
```

**JavaScript:**

```javascript
const response = await fetch("http://localhost:8765", {
  method: "POST",
  body: JSON.stringify({
    action: "addAudioNote",
    version: 5,
    params: {
      note: {
        deckName: "French",
        modelName: "Basic",
        fields: { Audio: "Bonjour", Front: "Hello" },
        tags: ["audio"],
      },
      language: "fr",
      gender: "male",
    },
  }),
});
const result = await response.json();
```
