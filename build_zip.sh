#!/usr/bin/bash
rm AnkiConnect.zip
cp AnkiConnect.py __init__.py
7za a AnkiConnect.zip __init__.py manifest.json profile_manager.py note_manager.py study_manager.py
rm __init__.py
