# -*- coding: utf-8 -*-
import unittest
from unittest import TestCase
from util import callAnkiConnectEndpoint

class TestDeckNames(TestCase):

    def test_deckNames(self):
        response = callAnkiConnectEndpoint({'action': 'deckNames'})
        self.assertEqual(['Default'], response)

class TestGetDeckConfig(TestCase):
    
    def test_getDeckConfig(self):
        response = callAnkiConnectEndpoint({'action': 'getDeckConfig', 'params': {'deck': 'Default'}})
        self.assertDictContainsSubset({'name': 'Default', 'replayq': True}, response)

RESET_OWNER = 'test_resetDecks'
RESET_OTHER = 'test_resetDecks_other'  # shares the owner's prefix, but not its '::'
RESET_TEXT = RESET_OWNER + '::Text'
RESET_AUDIO = RESET_OWNER + '::Audio'
RESET_LIBRARY = RESET_OWNER + '::French 10K'
RESET_UPLOAD = RESET_OWNER + '::Upload'
RESET_NESTED = RESET_OWNER + '::Upload::Nested'
RESET_KEEP = [RESET_OWNER, RESET_TEXT, RESET_AUDIO]

class TestResetDecks(TestCase):

    def setUp(self):
        # One note in every deck except the implicit parent RESET_UPLOAD.
        for deckName in [RESET_OWNER, RESET_TEXT, RESET_AUDIO, RESET_LIBRARY, RESET_NESTED, RESET_OTHER]:
            callAnkiConnectEndpoint({'action': 'createDeck', 'params': {'deckName': deckName}})
            callAnkiConnectEndpoint({'action': 'addNote', 'params': {'note': {
                'deckName': deckName,
                'modelName': 'Basic',
                'fields': {'Front': 'resetDecks ' + deckName, 'Back': 'back'},
            }}})

    def tearDown(self):
        for deckName in [RESET_OWNER, RESET_OTHER]:
            callAnkiConnectEndpoint({'action': 'deleteDeck', 'params': {'deckName': deckName}})

    def resetDecks(self, deckNames, ownerDeck=RESET_OWNER, keepDeckNames=RESET_KEEP):
        return callAnkiConnectEndpoint({'action': 'resetDecks', 'version': 6, 'params': {
            'ownerDeck': ownerDeck,
            'deckNames': deckNames,
            'keepDeckNames': keepDeckNames,
        }})

    def cardsInDeck(self, deckName):
        # deck:"X" alone would include X's subdecks
        query = 'deck:"%s" -deck:"%s::*"' % (deckName, deckName)
        return callAnkiConnectEndpoint({'action': 'findCards', 'params': {'query': query}})

    def test_resetAll(self):
        response = self.resetDecks([RESET_OWNER])
        self.assertIsNone(response['error'])
        result = response['result']
        self.assertEqual(5, result['notesDeleted'])
        self.assertEqual(5, len(result['deletedNoteIds']))
        self.assertEqual(sorted([RESET_LIBRARY, RESET_UPLOAD, RESET_NESTED]), sorted(result['decksRemoved']))
        self.assertEqual([], result['missing'])

        deckNames = callAnkiConnectEndpoint({'action': 'deckNames'})
        for deckName in RESET_KEEP:
            self.assertIn(deckName, deckNames)
            self.assertEqual([], self.cardsInDeck(deckName))
        for deckName in [RESET_LIBRARY, RESET_UPLOAD, RESET_NESTED]:
            self.assertNotIn(deckName, deckNames)
        self.assertEqual(1, len(self.cardsInDeck(RESET_OTHER)))

    def test_resetLibraryDeck(self):
        response = self.resetDecks([RESET_LIBRARY])
        self.assertIsNone(response['error'])
        result = response['result']
        self.assertEqual(1, result['notesDeleted'])
        self.assertEqual([RESET_LIBRARY], result['decksRemoved'])
        self.assertEqual([], result['missing'])

        deckNames = callAnkiConnectEndpoint({'action': 'deckNames'})
        self.assertNotIn(RESET_LIBRARY, deckNames)
        for deckName in [RESET_OWNER, RESET_TEXT, RESET_AUDIO, RESET_NESTED]:
            self.assertEqual(1, len(self.cardsInDeck(deckName)))

    def test_resetIsCaseInsensitive(self):
        response = self.resetDecks([RESET_LIBRARY.upper()])
        self.assertIsNone(response['error'])
        # decksRemoved reports Anki's own spelling of the name
        self.assertEqual([RESET_LIBRARY], response['result']['decksRemoved'])

    def test_resetTextKeepsDeckIdAndOptions(self):
        callAnkiConnectEndpoint({'action': 'setDeckStudyOptions', 'params': {
            'deckName': RESET_TEXT, 'newCardsPerDay': 7,
        }})
        deckIdBefore = callAnkiConnectEndpoint({'action': 'deckNamesAndIds'})[RESET_TEXT]
        configBefore = callAnkiConnectEndpoint({'action': 'getDeckConfig', 'params': {'deck': RESET_TEXT}})

        response = self.resetDecks([RESET_TEXT])
        self.assertIsNone(response['error'])
        result = response['result']
        self.assertEqual(1, result['notesDeleted'])
        self.assertEqual([], result['decksRemoved'])

        self.assertEqual(deckIdBefore, callAnkiConnectEndpoint({'action': 'deckNamesAndIds'})[RESET_TEXT])
        configAfter = callAnkiConnectEndpoint({'action': 'getDeckConfig', 'params': {'deck': RESET_TEXT}})
        self.assertEqual(configBefore['id'], configAfter['id'])
        self.assertEqual(7, configAfter['new']['perDay'])
        self.assertEqual([], self.cardsInDeck(RESET_TEXT))
        self.assertEqual(1, len(self.cardsInDeck(RESET_AUDIO)))

    def test_resetRemovesFilteredDecks(self):
        # Answer the Text card "Again" so a forgotten-cards filtered deck can pull it in.
        card = callAnkiConnectEndpoint({'action': 'getNextReviewCard', 'params': {'deckName': RESET_TEXT}})
        callAnkiConnectEndpoint({'action': 'answerCard', 'params': {'cardId': card['cardId'], 'ease': 1}})
        filteredDeck = RESET_OWNER + '::Text_StudyForgottenDays'
        callAnkiConnectEndpoint({'action': 'enableStudyForgotten', 'params': {
            'deckName': RESET_TEXT, 'days': 1, 'filteredDeckName': filteredDeck,
        }})
        self.assertIn(filteredDeck, callAnkiConnectEndpoint({'action': 'deckNames'}))

        # Resetting Audio alone still removes every filtered deck under the owner,
        # and the Text card it held goes back to Text instead of being deleted.
        response = self.resetDecks([RESET_AUDIO])
        self.assertIsNone(response['error'])
        result = response['result']
        self.assertEqual(1, result['notesDeleted'])
        self.assertEqual([filteredDeck], result['decksRemoved'])

        self.assertNotIn(filteredDeck, callAnkiConnectEndpoint({'action': 'deckNames'}))
        self.assertEqual([card['cardId']], self.cardsInDeck(RESET_TEXT))
        self.assertEqual([], self.cardsInDeck(RESET_AUDIO))

    def test_resetRejectsForeignDeck(self):
        response = self.resetDecks([RESET_OTHER])
        self.assertIsNone(response['result'])
        self.assertEqual("Deck '%s' does not belong to deck '%s'" % (RESET_OTHER, RESET_OWNER), response['error'])

        response = self.resetDecks([RESET_TEXT], keepDeckNames=RESET_KEEP + [RESET_OTHER])
        self.assertIsNone(response['result'])
        self.assertEqual("Deck '%s' does not belong to deck '%s'" % (RESET_OTHER, RESET_OWNER), response['error'])

        # Nothing was touched
        self.assertEqual(1, len(self.cardsInDeck(RESET_OTHER)))
        self.assertEqual(1, len(self.cardsInDeck(RESET_TEXT)))

    def test_resetReportsMissingDecks(self):
        absentDeck = RESET_OWNER + '::Absent'
        response = self.resetDecks([RESET_LIBRARY, absentDeck])
        self.assertIsNone(response['error'])
        result = response['result']
        self.assertEqual(1, result['notesDeleted'])
        self.assertEqual([RESET_LIBRARY], result['decksRemoved'])
        self.assertEqual([absentDeck], result['missing'])

    def test_resetMissingOwner(self):
        absentOwner = 'test_resetDecks_absent'
        deckNames = [absentOwner, absentOwner + '::Text']
        response = self.resetDecks(deckNames, ownerDeck=absentOwner, keepDeckNames=deckNames)
        self.assertIsNone(response['error'])
        self.assertEqual({
            'notesDeleted': 0,
            'deletedNoteIds': [],
            'decksRemoved': [],
            'missing': deckNames,
        }, response['result'])
