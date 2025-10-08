# AnkiConnect Profile Management Features

## Overview

AnkiConnect has been extended with new profile management capabilities that allow you to:

- Get information about the current profile
- List all available profiles
- Switch between different Anki profiles programmatically

## New API Methods

### 1. getCurrentProfile()

**Description**: Get information about the currently active profile.

**Request**:

```json
{
  "action": "getCurrentProfile",
  "version": 6
}
```

**Response**:

```json
{
  "result": {
    "name": "User 1",
    "path": "/path/to/profile/folder",
    "isDefault": true
  },
  "error": null
}
```

**Response Fields**:

- `name`: The name of the current profile
- `path`: File system path to the profile folder (if available)
- `isDefault`: Boolean indicating if this is the default "User 1" profile

### 2. getProfiles()

**Description**: Get a list of all available Anki profiles.

**Request**:

```json
{
  "action": "getProfiles",
  "version": 6
}
```

**Response**:

```json
{
  "result": [
    { "name": "User 1" },
    { "name": "Study Profile" },
    { "name": "Work Profile" }
  ],
  "error": null
}
```

### 3. switchProfile(profileName)

**Description**: Switch to a different Anki profile.

**Request**:

```json
{
  "action": "switchProfile",
  "version": 6,
  "params": {
    "profileName": "Study Profile"
  }
}
```

**Response (Success)**:

```json
{
  "result": {
    "success": true,
    "message": "Switched to profile: Study Profile"
  },
  "error": null
}
```

**Response (Error)**:

```json
{
  "result": {
    "error": "Profile \"NonExistent\" not found. Available profiles: [\"User 1\", \"Study Profile\"]"
  },
  "error": null
}
```

### 4. createProfile(profileName)

**Description**: Create a new Anki profile.

**Request**:

```json
{
  "action": "createProfile",
  "version": 6,
  "params": {
    "profileName": "New Study Profile"
  }
}
```

**Response (Success)**:

```json
{
  "result": {
    "success": true,
    "message": "Profile \"New Study Profile\" created successfully"
  },
  "error": null
}
```

**Response (Error - Profile Already Exists)**:

```json
{
  "result": {
    "error": "Profile \"New Study Profile\" already exists. Existing profiles: [\"User 1\", \"Study Profile\"]"
  },
  "error": null
}
```

**Response (Error - Invalid Name)**:

```json
{
  "result": {
    "error": "Profile name contains invalid characters. Avoid: ['/', '\\\\', ':', '*', '?', '\"', '<', '>', '|']"
  },
  "error": null
}
```

## Usage Examples

### Python Example

```python
import json
import urllib.request

def invoke(action, **params):
    requestJson = json.dumps({'action': action, 'params': params, 'version': 6})
    response = urllib.request.urlopen(urllib.request.Request('http://localhost:8765', requestJson.encode('utf-8')))
    return json.load(response)['result']

# Get current profile
current = invoke('getCurrentProfile')
print(f"Current profile: {current['name']}")

# List all profiles
profiles = invoke('getProfiles')
print("Available profiles:")
for profile in profiles:
    print(f"  - {profile['name']}")

# Switch to a different profile
result = invoke('switchProfile', profileName='Study Profile')
if 'success' in result:
    print(result['message'])
else:
    print(f"Error: {result['error']}")

# Create a new profile
result = invoke('createProfile', profileName='New Work Profile')
if 'success' in result:
    print(result['message'])
else:
    print(f"Error: {result['error']}")
```

### JavaScript Example

```javascript
async function invoke(action, params = {}) {
  const response = await fetch("http://localhost:8765", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action, params, version: 6 }),
  });
  return (await response.json()).result;
}

// Get current profile
const current = await invoke("getCurrentProfile");
console.log(`Current profile: ${current.name}`);

// List all profiles
const profiles = await invoke("getProfiles");
console.log(
  "Available profiles:",
  profiles.map((p) => p.name)
);

// Switch profile
const result = await invoke("switchProfile", { profileName: "Work Profile" });
console.log(result.success ? result.message : result.error);
```

### cURL Example

```bash
# Get current profile
curl -X POST http://localhost:8765 \
  -H "Content-Type: application/json" \
  -d '{"action": "getCurrentProfile", "version": 6}'

# Get all profiles
curl -X POST http://localhost:8765 \
  -H "Content-Type: application/json" \
  -d '{"action": "getProfiles", "version": 6}'

# Switch profile
curl -X POST http://localhost:8765 \
  -H "Content-Type: application/json" \
  -d '{"action": "switchProfile", "version": 6, "params": {"profileName": "Study Profile"}}'
```

## Important Notes

### Profile Switching Behavior

- Profile switching may require Anki to restart or reload collections
- Some Anki versions may not support programmatic profile switching
- Always check the response for success/error status

### Error Handling

- If a profile doesn't exist, you'll get an error with available profiles listed
- If profile management is not available, you'll get an appropriate error message
- Network errors should be handled at the client level

### Compatibility

- These features require the updated AnkiConnect addon
- Compatible with Anki 25.x (PyQt6) and older versions (PyQt5)
- API version 6 recommended for full feature support

## Troubleshooting

### Common Issues

1. **"Profile manager not available"**

   - This may occur if Anki's profile system is not accessible
   - Try restarting Anki and the AnkiConnect addon

2. **"Profile switching not supported"**

   - Some Anki versions may not support programmatic profile switching
   - Manual profile switching through Anki's interface may be required

3. **Profile not found errors**
   - Use `getProfiles()` to see available profile names
   - Profile names are case-sensitive

### Testing Profile Features

```python
# Test script to verify profile management works
def test_profile_management():
    try:
        # Test getting current profile
        current = invoke('getCurrentProfile')
        print(f"✓ Current profile: {current}")

        # Test listing profiles
        profiles = invoke('getProfiles')
        print(f"✓ Available profiles: {profiles}")

        # Test switching (if multiple profiles exist)
        if len(profiles) > 1:
            target_profile = profiles[1]['name']  # Switch to second profile
            result = invoke('switchProfile', profileName=target_profile)
            print(f"✓ Switch result: {result}")

        print("All profile management features working!")

    except Exception as e:
        print(f"✗ Error testing profile management: {e}")

test_profile_management()
```

## Installation

1. Install the updated AnkiConnect.zip addon package
2. Restart Anki
3. The new profile management methods will be available via the AnkiConnect API

The profile management features are now ready to use!
