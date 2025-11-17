#!/usr/bin/bash

# Read current version from manifest.json
CURRENT_VERSION=$(grep -o '"version": "[^"]*"' manifest.json | cut -d'"' -f4)
echo "Current version: $CURRENT_VERSION"

# Ask for new version
read -p "Enter new version (press Enter to keep $CURRENT_VERSION): " NEW_VERSION

# If no version entered, keep the current version
if [ -z "$NEW_VERSION" ]; then
    NEW_VERSION=$CURRENT_VERSION
    echo "Keeping current version: $NEW_VERSION"
else
    echo "Updating version to: $NEW_VERSION"
fi

# Update version field in manifest.json
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    sed -i '' "s/\"version\": \"$CURRENT_VERSION\"/\"version\": \"$NEW_VERSION\"/" manifest.json
else
    # Linux
    sed -i "s/\"version\": \"$CURRENT_VERSION\"/\"version\": \"$NEW_VERSION\"/" manifest.json
fi

# Update version in the name field of manifest.json
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    sed -i '' "s/Global Edge Anki Connect v$CURRENT_VERSION/Global Edge Anki Connect v$NEW_VERSION/" manifest.json
else
    # Linux
    sed -i "s/Global Edge Anki Connect v$CURRENT_VERSION/Global Edge Anki Connect v$NEW_VERSION/" manifest.json
fi

# Update version in AnkiConnect.py
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    sed -i '' "s/ADDON_VERSION = \"$CURRENT_VERSION\"/ADDON_VERSION = \"$NEW_VERSION\"/" AnkiConnect.py
else
    # Linux
    sed -i "s/ADDON_VERSION = \"$CURRENT_VERSION\"/ADDON_VERSION = \"$NEW_VERSION\"/" AnkiConnect.py
fi

echo "Version updated to $NEW_VERSION in manifest.json and AnkiConnect.py"

# Build the zip file
rm -f GlobalEdgeAnkiConnect.zip
cp AnkiConnect.py __init__.py
7za a GlobalEdgeAnkiConnect.zip __init__.py manifest.json profile_manager.py note_manager.py study_manager.py
rm __init__.py

echo "Build complete! GlobalEdgeAnkiConnect.zip created with version $NEW_VERSION"
