#!/usr/bin/env python3
"""Fail if a deprecated Anki API call reappears on a live endpoint.

Anki routes every legacy name through DeprecatedNamesMixin.__getattr__, which
calls traceback.extract_stack() (~28us, linecache source reads included) and
print()s to stdout -- on every call, on every request. notesInfo used to pay
this twice per note.

Scope is deliberately the endpoints studyplan2021 actually calls. Dead
endpoints keep their legacy calls; they cost nothing if never invoked, so
flagging them would just be noise. Add an action to LIVE_ACTIONS when the
client starts calling it.

Static only -- no Anki, no collection, no running server. Run directly:

    python3 tests/check_deprecated_apis.py
"""

import ast
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Actions studyplan2021 calls today: ANKI_ACTIONS in src/services/ankiService.js
# plus raw action: strings in src/config/cron.js, controllers/status/getStatus.js
# and controllers/anki/*.js.
LIVE_ACTIONS = {
    'addAudioNote', 'addNote', 'answerCard', 'createDeck', 'createModel',
    'deleteDeck', 'deleteNote', 'enableStudyForgotten', 'extendNewCardLimit',
    'flagCard', 'getDeckInfo', 'getDeckReviewsByDayMulti', 'getNextReviewCard',
    'getNoteIds', 'importPackage', 'modelNamesAndIds', 'multi', 'notesInfo',
    'resetDecks', 'setDeckStudyOptions', 'undoAnswerCard', 'unflagCard', 'updateModel',
    'updateNoteFields', 'version',
}

# Live but not endpoints: module-level helpers reached from a live handler.
# All three are called by setDeckStudyOptions (managers/study_manager.py).
LIVE_HELPERS = {
    'utils/deck_helpers.py': {
        'get_direct_child_decks', 'get_deck_limits', 'update_parent_deck_silent',
    },
}

FILES = [
    'AnkiConnect.py',
    'managers/note_manager.py',
    'managers/study_manager.py',
    'utils/deck_helpers.py',
]

# Legacy name -> what to use instead. Only names that actually emit a warning in
# Anki 25.09.2, via __getattr__ snakecase, a register_deprecated_aliases entry,
# or a live @deprecated decorator.
#
# Deliberately absent: sched.forgetCards, sched.remFromDyn, models.addField,
# models.remField, models.addTemplate, models.remTemplate, collection.addNote,
# note.dupeOrEmpty. Those resolve through plain class attributes or @deprecated
# decorators that are commented out upstream -- legacy, but silent and free.
BANNED = {
    'getNote': 'collection.get_note()',
    'getCard': 'collection.get_card()',
    'remNotes': 'collection.remove_notes()',
    'findCards': 'collection.find_cards()',
    'findNotes': 'collection.find_notes()',
    'model': 'note.note_type() / card.note_type()',
    'byName': 'by_name()',
    'allNames': 'all_names_and_ids() (returns objects; take .name)',
    'getConf': 'decks.get_config()',
    'confForDid': 'decks.config_dict_for_deck_id()',
    'confId': 'decks.add_config_returning_id()',
    'remConf': 'decks.remove_config()',
    'newField': 'models.new_field()',
    'newTemplate': 'models.new_template()',
    'useCount': 'models.use_count()',
    'rem': 'decks.remove([did]) / models.remove(id)',
    'suspendCards': 'sched.suspend_cards()',
    'unsuspendCards': 'sched.unsuspend_cards()',
    'bulkAdd': 'tags.bulk_add()',
    'startTimer': 'card.start_timer()',
}

DECKS_DICT_HINT = (
    'decks.decks is a DecksDictProxy: it warns and calls decks.all(), '
    'materialising every deck. Use decks.children() / deck_and_child_ids() / '
    'all_names_and_ids() instead.'
)


def enclosing_functions(tree):
    """Map line number -> name of the innermost function containing it."""
    owner = {}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        span = (node.end_lineno or node.lineno) - node.lineno
        for line in range(node.lineno, (node.end_lineno or node.lineno) + 1):
            prev = owner.get(line)
            if prev is None or span < prev[1]:
                owner[line] = (node.name, span)
    return {line: name for line, (name, _span) in owner.items()}


def check_file(rel):
    """Return a list of (line, function, message) for one file."""
    path = os.path.join(REPO, rel)
    tree = ast.parse(open(path, encoding='utf-8').read(), filename=rel)
    owner = enclosing_functions(tree)
    live = LIVE_ACTIONS | LIVE_HELPERS.get(rel, set())

    # Only flag attributes that are actually called -- `foo.model()` is a
    # deprecated method, but a bare `params.model` is just data.
    called = {id(n.func) for n in ast.walk(tree) if isinstance(n, ast.Call)}

    findings = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute):
            continue
        fn = owner.get(node.lineno)
        if fn not in live:
            continue

        # decks.decks -- an attribute chain, never a call
        if (node.attr == 'decks' and isinstance(node.value, ast.Attribute)
                and node.value.attr == 'decks'):
            findings.append((node.lineno, fn, DECKS_DICT_HINT))
            continue

        if node.attr in BANNED and id(node) in called:
            findings.append((
                node.lineno, fn,
                '{} is deprecated -- use {}'.format(node.attr, BANNED[node.attr]),
            ))
    return findings


def main():
    total = 0
    for rel in FILES:
        for line, fn, msg in sorted(check_file(rel)):
            print('{}:{}: [{}] {}'.format(rel, line, fn, msg))
            total += 1

    if total:
        print('\n{} deprecated call(s) on live endpoints.'.format(total))
        return 1
    print('OK: no deprecated Anki API calls on live endpoints '
          '({} files checked).'.format(len(FILES)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
