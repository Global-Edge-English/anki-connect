# Graph Report - .  (2026-04-15)

## Corpus Check
- Corpus is ~28,355 words - fits in a single context window. You may not need a graph.

## Summary
- 338 nodes · 580 edges · 23 communities detected
- Extraction: 86% EXTRACTED · 14% INFERRED · 0% AMBIGUOUS · INFERRED: 84 edges (avg confidence: 0.71)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_AnkiBridge Core API|AnkiBridge Core API]]
- [[_COMMUNITY_Study & Review Engine|Study & Review Engine]]
- [[_COMMUNITY_HTTP Server & Routing|HTTP Server & Routing]]
- [[_COMMUNITY_Card Operations|Card Operations]]
- [[_COMMUNITY_CRUD Models & Decks|CRUD Models & Decks]]
- [[_COMMUNITY_Note Creation Pipeline|Note Creation Pipeline]]
- [[_COMMUNITY_Deck & Misc Tests|Deck & Misc Tests]]
- [[_COMMUNITY_Documentation Hub|Documentation Hub]]
- [[_COMMUNITY_Custom Study & Tracking|Custom Study & Tracking]]
- [[_COMMUNITY_Answer Card Tests|Answer Card Tests]]
- [[_COMMUNITY_Delete Operations|Delete Operations]]
- [[_COMMUNITY_Server Rationale|Server Rationale]]
- [[_COMMUNITY_Note ID Lookup|Note ID Lookup]]
- [[_COMMUNITY_Model Creation|Model Creation]]
- [[_COMMUNITY_Model Deletion|Model Deletion]]
- [[_COMMUNITY_Model Info|Model Info]]
- [[_COMMUNITY_Deck Creation|Deck Creation]]
- [[_COMMUNITY_Deck Renaming|Deck Renaming]]
- [[_COMMUNITY_Deck Info|Deck Info]]
- [[_COMMUNITY_Current Profile|Current Profile]]
- [[_COMMUNITY_Profile Listing|Profile Listing]]
- [[_COMMUNITY_Profile Switching|Profile Switching]]
- [[_COMMUNITY_Profile Creation|Profile Creation]]

## God Nodes (most connected - your core abstractions)
1. `AnkiBridge` - 63 edges
2. `AjaxServer` - 39 edges
3. `StudyManager` - 35 edges
4. `NoteManager` - 26 edges
5. `AnkiNoteParams` - 8 edges
6. `AjaxClient` - 7 edges
7. `makeBytes()` - 7 edges
8. `addNote()` - 6 edges
9. `findCards()` - 6 edges
10. `makeStr()` - 6 edges

## Surprising Connections (you probably didn't know these)
- `Decorator for marking API methods` --uses--> `AjaxServer`  [INFERRED]
  AnkiConnect.py → utils/network.py
- `Add a note with audio file from URL                  Args:             params: N` --uses--> `AjaxServer`  [INFERRED]
  AnkiConnect.py → utils/network.py
- `parseMultipartData()` --calls--> `makeStr()`  [INFERRED]
  AnkiConnect.py → utils/helpers.py
- `AnkiNoteParams` --uses--> `AjaxServer`  [INFERRED]
  AnkiConnect.py → utils/network.py
- `AnkiBridge` --uses--> `AjaxServer`  [INFERRED]
  AnkiConnect.py → utils/network.py

## Hyperedges (group relationships)
- **Card Review Lifecycle** — button_timings_feature, answer_card_time_tracking, note_deck_apis_undoAnswerCard, revlog_table [INFERRED 0.85]
- **Custom Study Operations Bundle** — custom_study_setDeckStudyOptions, custom_study_extendNewCardLimit, custom_study_enableStudyForgotten, custom_study_createCustomStudy [EXTRACTED 1.00]
- **Note Creation Pipeline** — audio_notes_addAudioNote, deck_name_fix, update_note_fields_api, anki_note_card_data_model [INFERRED 0.80]

## Communities

### Community 0 - "AnkiBridge Core API"
Cohesion: 0.07
Nodes (7): AnkiBridge, changeDeck(), deckNames(), findCards(), guiDeckOverview(), Flag a card with red flag (flag value 1), Remove flag from a card (set flag value to 0)

### Community 1 - "Study & Review Engine"
Cohesion: 0.05
Nodes (39): answerCard(), createCustomStudy(), enableStudyForgotten(), extendNewCardLimit(), forgetCard(), getDeckReviewsByDay(), getDeckTimeStats(), getDueCards() (+31 more)

### Community 2 - "HTTP Server & Routing"
Cohesion: 0.05
Nodes (33): AnkiConnect, parseMultipartData(), Import an Anki package (.apkg) from a URL using the modern backend API, Parse multipart/form-data request body          Args:         body: Request body, Update note fields with optional audio download and deck validation (unified API, Get the add-on version, Debug endpoint to check what methods are available, Add a note with audio file from URL                  Args:             note: Not (+25 more)

### Community 3 - "Card Operations"
Cohesion: 0.04
Nodes (9): addTags(), deleteMediaFile(), findNotes(), modelNames(), Decorator for marking API methods, removeTags(), suspend(), unsuspend() (+1 more)

### Community 4 - "CRUD Models & Decks"
Cohesion: 0.09
Nodes (24): createDeck(), createModel(), deleteDeck(), deleteModel(), deleteNote(), getDeckInfo(), getModelInfo(), getNoteIds() (+16 more)

### Community 5 - "Note Creation Pipeline"
Cohesion: 0.15
Nodes (16): addNote(), addNotes(), AnkiNoteParams, canAddNotes(), Add a note with audio file from URL                  Args:             params: N, upgrade(), audioInject(), download() (+8 more)

### Community 6 - "Deck & Misc Tests"
Cohesion: 0.24
Nodes (5): TestDeckNames, TestGetDeckConfig, TestVersion, TestCase, callAnkiConnectEndpoint()

### Community 7 - "Documentation Hub"
Cohesion: 0.22
Nodes (10): Anki Note-Card Data Model, addAudioNote API, Deck Name Fix - Notes Added to Wrong Deck, Deck Name Fix Rationale - Modern API vs Deprecated, updateModel API, AnkiConnect Plugin, updateModel Bug Fix, updateModel Fix Rationale - Reverse Order Removal (+2 more)

### Community 8 - "Custom Study & Tracking"
Cohesion: 0.25
Nodes (9): answerCard Time Tracking, Button Timings Feature, createCustomStudy API, enableStudyForgotten API, extendNewCardLimit API, setDeckStudyOptions API, undoAnswerCard API, Revlog Table (Review Log) (+1 more)

### Community 9 - "Answer Card Tests"
Cohesion: 0.67
Nodes (2): Test the answerCard API, test_api()

### Community 10 - "Delete Operations"
Cohesion: 1.0
Nodes (2): deleteNote API, deleteDeck API

### Community 11 - "Server Rationale"
Cohesion: 1.0
Nodes (1): Create a filtered deck for studying cards that were forgotten (answered "Again")

### Community 12 - "Note ID Lookup"
Cohesion: 1.0
Nodes (1): getNoteIds API

### Community 13 - "Model Creation"
Cohesion: 1.0
Nodes (1): createModel API

### Community 14 - "Model Deletion"
Cohesion: 1.0
Nodes (1): deleteModel API

### Community 15 - "Model Info"
Cohesion: 1.0
Nodes (1): getModelInfo API

### Community 16 - "Deck Creation"
Cohesion: 1.0
Nodes (1): createDeck API

### Community 17 - "Deck Renaming"
Cohesion: 1.0
Nodes (1): renameDeck API

### Community 18 - "Deck Info"
Cohesion: 1.0
Nodes (1): getDeckInfo API

### Community 19 - "Current Profile"
Cohesion: 1.0
Nodes (1): getCurrentProfile API

### Community 20 - "Profile Listing"
Cohesion: 1.0
Nodes (1): getProfiles API

### Community 21 - "Profile Switching"
Cohesion: 1.0
Nodes (1): switchProfile API

### Community 22 - "Profile Creation"
Cohesion: 1.0
Nodes (1): createProfile API

## Knowledge Gaps
- **84 isolated node(s):** `Flag a card with red flag (flag value 1)`, `Remove flag from a card (set flag value to 0)`, `Update note fields with optional audio download and deck validation (unified API`, `Get the add-on version`, `Debug endpoint to check what methods are available` (+79 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Delete Operations`** (2 nodes): `deleteNote API`, `deleteDeck API`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Server Rationale`** (1 nodes): `Create a filtered deck for studying cards that were forgotten (answered "Again")`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Note ID Lookup`** (1 nodes): `getNoteIds API`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Model Creation`** (1 nodes): `createModel API`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Model Deletion`** (1 nodes): `deleteModel API`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Model Info`** (1 nodes): `getModelInfo API`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Deck Creation`** (1 nodes): `createDeck API`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Deck Renaming`** (1 nodes): `renameDeck API`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Deck Info`** (1 nodes): `getDeckInfo API`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Current Profile`** (1 nodes): `getCurrentProfile API`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Profile Listing`** (1 nodes): `getProfiles API`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Profile Switching`** (1 nodes): `switchProfile API`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Profile Creation`** (1 nodes): `createProfile API`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `AnkiBridge` connect `AnkiBridge Core API` to `HTTP Server & Routing`, `Card Operations`, `Note Creation Pipeline`?**
  _High betweenness centrality (0.272) - this node is a cross-community bridge._
- **Why does `AjaxServer` connect `HTTP Server & Routing` to `AnkiBridge Core API`, `Card Operations`, `Note Creation Pipeline`?**
  _High betweenness centrality (0.183) - this node is a cross-community bridge._
- **Are the 25 inferred relationships involving `AjaxServer` (e.g. with `AnkiNoteParams` and `AnkiBridge`) actually correct?**
  _`AjaxServer` has 25 INFERRED edges - model-reasoned connections that need verification._
- **Are the 14 inferred relationships involving `StudyManager` (e.g. with `getNextReviewCard()` and `answerCard()`) actually correct?**
  _`StudyManager` has 14 INFERRED edges - model-reasoned connections that need verification._
- **Are the 10 inferred relationships involving `NoteManager` (e.g. with `createModel()` and `updateModel()`) actually correct?**
  _`NoteManager` has 10 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Flag a card with red flag (flag value 1)`, `Remove flag from a card (set flag value to 0)`, `Update note fields with optional audio download and deck validation (unified API` to the rest of the system?**
  _84 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `AnkiBridge Core API` be split into smaller, more focused modules?**
  _Cohesion score 0.07 - nodes in this community are weakly interconnected._