# AnkiConnect GlobalEdge

## Project Overview

A customized fork of [AnkiConnect](https://foosoft.net/projects/anki-connect/) — an Anki add-on that exposes Anki functionality over a local HTTP API (port 8765). This version is branded "Global Edge Anki Connect" and adds study management, note management, and audio injection features on top of the original AnkiConnect.

- **Language:** Python (Anki add-on)
- **Current version:** defined in `manifest.json` and `AnkiConnect.py` (`ADDON_VERSION`)
- **API version:** 5

## Architecture

- `AnkiConnect.py` — Main entry point. HTTP request handler, API action dispatch, and core Anki operations.
- `managers/` — Domain logic split into:
  - `note_manager.py` — Note/card operations
  - `study_manager.py` — Study session and scheduling logic
- `utils/` — Shared helpers:
  - `helpers.py` — String utils, download, MIME type, audio injection
  - `network.py` — `AjaxServer` HTTP server implementation
  - `deck_helpers.py` — Deck-related utilities
- `tests/` — Test files (`test_answer_card.py`, `test_decks.py`, `test_misc.py`)

## Building

Run `build_zip.sh` to package the add-on. It:
1. Prompts for a version bump (updates `manifest.json` and `AnkiConnect.py`)
2. Copies `AnkiConnect.py` to `__init__.py`
3. Zips into `GlobalEdgeAnkiConnect.zip` using `7za`

## Development Notes

- The add-on runs inside Anki's Python environment (`anki`, `aqt` modules).
- Tests use a Docker-based setup (see `tests/docker/`).
- Keep import fallback chains in `AnkiConnect.py` intact — they handle different execution contexts.
- Version must stay in sync between `manifest.json` (`version` and `name` fields) and `AnkiConnect.py` (`ADDON_VERSION`). Use `build_zip.sh` to update.

## graphify

When the user types `/graphify`, invoke the Skill tool with `skill: "graphify"` before doing anything else.
