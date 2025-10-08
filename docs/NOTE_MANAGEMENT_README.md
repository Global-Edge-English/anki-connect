# Note Type and Deck Management with AnkiConnect

This document explains how to use the enhanced AnkiConnect API to create, modify, and delete note types (models) and decks programmatically.

## New API Actions

### Note Type (Model) Management

#### createModel

Creates a new note type with specified fields, templates, and styling.

**Parameters:**

- `modelName` (string): Name of the new note type
- `fields` (array): List of field names
- `templates` (array): List of template objects with `name`, `qfmt`, `afmt`
- `css` (string, optional): CSS styling for the note type

**Example:**

```json
{
  "action": "createModel",
  "version": 5,
  "params": {
    "modelName": "Language Learning",
    "fields": ["Word", "Definition", "Example", "Audio"],
    "templates": [
      {
        "name": "Card 1",
        "qfmt": "{{Word}}",
        "afmt": "{{Definition}}<br>{{Example}}<br>{{Audio}}"
      }
    ],
    "css": ".card { font-family: Arial; font-size: 20px; }"
  }
}
```

#### updateModel

Updates an existing note type. You can update the name, fields, templates, or CSS.

**Parameters:**

- `modelId` (int): ID of the model to update
- `modelName` (string, optional): New name for the model
- `fields` (array, optional): New list of field names
- `templates` (array, optional): New list of templates
- `css` (string, optional): New CSS styling

**Example:**

```json
{
  "action": "updateModel",
  "version": 5,
  "params": {
    "modelId": 1234567890,
    "modelName": "Advanced Language Learning",
    "fields": ["Word", "Definition", "Example", "Audio", "Context"],
    "css": ".card { font-family: Arial; font-size: 22px; color: #333; }"
  }
}
```

#### deleteModel

Deletes a note type. Cannot delete if notes are using this model.

**Parameters:**

- `modelId` (int): ID of the model to delete

**Example:**

```json
{
  "action": "deleteModel",
  "version": 5,
  "params": {
    "modelId": 1234567890
  }
}
```

#### getModelInfo

Gets detailed information about a model including fields, templates, CSS, and usage count.

**Parameters:**

- `modelId` (int): ID of the model

**Example:**

```json
{
  "action": "getModelInfo",
  "version": 5,
  "params": {
    "modelId": 1234567890
  }
}
```

**Response:**

```json
{
  "result": {
    "id": 1234567890,
    "name": "Language Learning",
    "fields": ["Word", "Definition", "Example", "Audio"],
    "templates": [
      {
        "name": "Card 1",
        "qfmt": "{{Word}}",
        "afmt": "{{Definition}}<br>{{Example}}<br>{{Audio}}"
      }
    ],
    "css": ".card { font-family: Arial; font-size: 20px; }",
    "noteCount": 42
  },
  "error": null
}
```

### Deck Management

#### createDeck

Creates a new deck with the specified name.

**Parameters:**

- `deckName` (string): Name of the new deck

**Example:**

```json
{
  "action": "createDeck",
  "version": 5,
  "params": {
    "deckName": "Spanish Vocabulary"
  }
}
```

#### deleteDeck

Deletes a deck and optionally its cards.

**Parameters:**

- `deckName` (string): Name of the deck to delete
- `deleteCards` (bool, optional): Whether to delete cards (default: false, moves to default deck)

**Example:**

```json
{
  "action": "deleteDeck",
  "version": 5,
  "params": {
    "deckName": "Old Deck",
    "deleteCards": true
  }
}
```

#### renameDeck

Renames an existing deck.

**Parameters:**

- `oldName` (string): Current deck name
- `newName` (string): New deck name

**Example:**

```json
{
  "action": "renameDeck",
  "version": 5,
  "params": {
    "oldName": "Spanish Vocab",
    "newName": "Spanish Vocabulary - Advanced"
  }
}
```

#### getDeckInfo

Gets detailed information about a deck including card counts.

**Parameters:**

- `deckName` (string): Name of the deck

**Example:**

```json
{
  "action": "getDeckInfo",
  "version": 5,
  "params": {
    "deckName": "Spanish Vocabulary"
  }
}
```

**Response:**

```json
{
  "result": {
    "id": 1234567890,
    "name": "Spanish Vocabulary",
    "newCount": 25,
    "learningCount": 12,
    "reviewCount": 150,
    "totalCards": 187
  },
  "error": null
}
```

## Complete Workflow Example

Here's a complete example of creating a custom note type, creating a deck, and adding notes:

### 1. Create Custom Note Type

```json
{
  "action": "createModel",
  "version": 5,
  "params": {
    "modelName": "Vocabulary Card",
    "fields": ["Term", "Definition", "Example", "Source"],
    "templates": [
      {
        "name": "Forward",
        "qfmt": "<div class='question'>{{Term}}</div>",
        "afmt": "<div class='answer'>{{Definition}}</div><hr><div class='example'>{{Example}}</div><div class='source'>Source: {{Source}}</div>"
      }
    ],
    "css": ".card { font-family: 'Arial'; text-align: center; } .question { font-size: 24px; font-weight: bold; } .answer { font-size: 18px; margin: 20px; } .example { font-style: italic; color: #666; } .source { font-size: 12px; color: #999; }"
  }
}
```

### 2. Create New Deck

```json
{
  "action": "createDeck",
  "version": 5,
  "params": {
    "deckName": "My Custom Vocabulary"
  }
}
```

### 3. Add Notes Using the Custom Type

```json
{
  "action": "addNote",
  "version": 5,
  "params": {
    "note": {
      "deckName": "My Custom Vocabulary",
      "modelName": "Vocabulary Card",
      "fields": {
        "Term": "serendipity",
        "Definition": "the occurrence and development of events by chance in a happy or beneficial way",
        "Example": "A fortunate stroke of serendipity brought the two old friends together.",
        "Source": "Dictionary.com"
      },
      "tags": ["vocabulary", "advanced"]
    }
  }
}
```

## Error Handling

All API actions return errors in a consistent format:

```json
{
  "result": null,
  "error": "Model 'Advanced Spanish' already exists"
}
```

Common errors:

- **Model/Deck already exists**: When trying to create something that already exists
- **Model/Deck not found**: When trying to modify/delete something that doesn't exist
- **Model in use**: When trying to delete a note type that has notes using it
- **Invalid parameters**: When required parameters are missing or invalid

## Best Practices

1. **Check existing models/decks** before creating new ones using `modelNames` and `deckNames`
2. **Use getModelInfo/getDeckInfo** to verify current state before making changes
3. **Handle errors gracefully** in your applications
4. **Test with small changes** before making bulk modifications
5. **Backup your collection** before making significant structural changes

## Python Example

```python
import requests
import json

def anki_connect_request(action, params=None, version=5):
    payload = {
        "action": action,
        "version": version
    }
    if params:
        payload["params"] = params

    response = requests.post("http://localhost:8765", json=payload)
    return response.json()

# Create a custom note type
model_result = anki_connect_request("createModel", {
    "modelName": "My Custom Type",
    "fields": ["Question", "Answer", "Extra"],
    "templates": [{
        "name": "Card 1",
        "qfmt": "{{Question}}",
        "afmt": "{{Answer}}<br>{{Extra}}"
    }],
    "css": ".card { font-family: Arial; }"
})

print(f"Model created with ID: {model_result['result']}")

# Create a deck
deck_result = anki_connect_request("createDeck", {
    "deckName": "My Custom Deck"
})

print(f"Deck created with ID: {deck_result['result']}")

# Add a note
note_result = anki_connect_request("addNote", {
    "note": {
        "deckName": "My Custom Deck",
        "modelName": "My Custom Type",
        "fields": {
            "Question": "What is the capital of France?",
            "Answer": "Paris",
            "Extra": "City of Light"
        }
    }
})

print(f"Note created with ID: {note_result['result']}")
```

This enhanced AnkiConnect functionality gives you complete programmatic control over your Anki collection structure, enabling powerful automation and custom applications.
