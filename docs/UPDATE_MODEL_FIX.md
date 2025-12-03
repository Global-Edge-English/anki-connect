# updateModel Bug Fix

## Summary

Fixed a critical bug in `managers/note_manager.py` that was causing the error:

```
"list.remove(x): x not in list"
```

## The Problem

The original `updateModel` method was trying to:

1. Remove ALL existing fields first
2. Then add all new fields

This caused the error because:

- The Python `list.remove()` method modifies the list while iterating
- Anki's internal field tracking gets out of sync
- When fields are used by existing notes, the removal fails

## The Solution

The fixed `updateModel` method now:

1. **Compares** old and new field lists
2. **Only removes** fields that are truly being deleted
3. **Only adds** fields that are truly new
4. **Reorders** remaining fields to match the desired order
5. Processes removals in **reverse order** to avoid index issues

## How to Use

### Example: Add New Fields to Existing Model

```bash
# Step 1: Get current model info
curl localhost:8765 -X POST -d '{
  "action": "getModelInfo",
  "version": 5,
  "params": {"modelId": 1760603648405}
}'

# Step 2: Update with new fields (all at once now works!)
curl localhost:8765 -X POST -d '{
  "action": "updateModel",
  "version": 5,
  "params": {
    "modelId": 1760603648405,
    "fields": [
      "Studypoint",
      "Example Sentence",
      "Hiragana",
      "Translation",
      "Definition",
      "Comments",
      "Part of Speech"
    ],
    "templates": [
      {
        "name": "StudypointCard",
        "qfmt": "<div>{{Studypoint}}</div><br>{{Example Sentence}}",
        "afmt": "{{FrontSide}}<hr>{{Part of Speech}}<br>{{Hiragana}}<br>{{Translation}}<br>{{Definition}}<br>{{Comments}}"
      }
    ]
  }
}'
```

### Example: Reorder Fields

```javascript
// JavaScript example
async function reorderFields(modelId, newOrder) {
  const response = await fetch("http://localhost:8765", {
    method: "POST",
    body: JSON.stringify({
      action: "updateModel",
      version: 5,
      params: {
        modelId: modelId,
        fields: newOrder, // Just specify the new order
      },
    }),
  });
  return await response.json();
}

// Usage
await reorderFields(1760603648405, [
  "Hiragana",
  "Translation",
  "Studypoint",
  "Definition",
  "Example Sentence",
  "Comments",
  "Part of Speech",
]);
```

### Example: Add Single Field

```python
import requests

def add_field_to_model(model_id, field_name):
    # Get current model info
    current = requests.post('http://localhost:8765', json={
        'action': 'getModelInfo',
        'version': 5,
        'params': {'modelId': model_id}
    }).json()

    current_fields = current['result']['fields']

    # Add new field
    new_fields = current_fields + [field_name]

    # Update model
    result = requests.post('http://localhost:8765', json={
        'action': 'updateModel',
        'version': 5,
        'params': {
            'modelId': model_id,
            'fields': new_fields
        }
    })

    return result.json()

# Usage
add_field_to_model(1760603648405, "Audio")
```

## What Changed in the Code

### Before (Buggy):

```python
# Update fields if provided
if fields is not None:
    # Remove existing fields
    for field in model['flds'][:]:
        collection.models.remField(model, field)

    # Add new fields
    for fieldName in fields:
        field = collection.models.newField(fieldName)
        collection.models.addField(model, field)
```

### After (Fixed):

```python
# Update fields if provided
if fields is not None:
    # Get current field names
    existing_field_names = [f['name'] for f in model['flds']]
    new_field_names = fields

    # Find fields to remove (in old but not in new)
    fields_to_remove = [f for f in model['flds'] if f['name'] not in new_field_names]

    # Find fields to add (in new but not in old)
    fields_to_add = [name for name in new_field_names if name not in existing_field_names]

    # Remove fields that are no longer needed (in reverse order to avoid index issues)
    for field in reversed(fields_to_remove):
        collection.models.remField(model, field)

    # Add new fields
    for fieldName in fields_to_add:
        field = collection.models.newField(fieldName)
        collection.models.addField(model, field)

    # Reorder fields to match the desired order
    field_map = {f['name']: f for f in model['flds']}
    reordered_fields = []
    for idx, fieldName in enumerate(new_field_names):
        if fieldName in field_map:
            field = field_map[fieldName]
            field['ord'] = idx
            reordered_fields.append(field)

    model['flds'] = reordered_fields
```

## Key Benefits

1. ✅ **No more "list.remove(x): x not in list" errors**
2. ✅ **Can add multiple fields at once**
3. ✅ **Can reorder fields safely**
4. ✅ **Preserves existing field data**
5. ✅ **Works with models that have existing notes**

## Testing

To verify the fix works:

```bash
# Test 1: Add new fields
curl localhost:8765 -X POST -d '{
  "action": "updateModel",
  "version": 5,
  "params": {
    "modelId": YOUR_MODEL_ID,
    "fields": ["Field1", "Field2", "NewField3"]
  }
}'

# Test 2: Reorder fields
curl localhost:8765 -X POST -d '{
  "action": "updateModel",
  "version": 5,
  "params": {
    "modelId": YOUR_MODEL_ID,
    "fields": ["Field2", "Field1", "NewField3"]
  }
}'

# Test 3: Remove a field
curl localhost:8765 -X POST -d '{
  "action": "updateModel",
  "version": 5,
  "params": {
    "modelId": YOUR_MODEL_ID,
    "fields": ["Field1", "Field2"]
  }
}'
```

## Related Documentation

- [NOTE_MANAGEMENT_README.md](./NOTE_MANAGEMENT_README.md) - General note management API
- [README.md](../README.md) - Main AnkiConnect documentation

## Date Fixed

December 3, 2025
