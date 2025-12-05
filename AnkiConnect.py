# Copyright (C) 2016 Alex Yatskov <alex@foosoft.net>
# Author: Alex Yatskov <alex@foosoft.net>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.


import anki
import aqt
import base64
import hashlib
import inspect
import json
import os
import os.path
import re
import sys
import tempfile
from time import time
from unicodedata import normalize
from operator import itemgetter

try:
    from .managers import NoteManager, StudyManager
except ImportError:
    # Fallback for older Python versions or different import contexts
    try:
        from managers import NoteManager, StudyManager
    except ImportError:
        # Final fallback for legacy structure
        import note_manager
        import study_manager
        NoteManager = note_manager.NoteManager
        StudyManager = study_manager.StudyManager

try:
    from .utils import (
        makeBytes, makeStr, download, verifyString, verifyStringList,
        getMimeType, audioInject, AjaxServer
    )
except ImportError:
    # Fallback for older Python versions or different import contexts
    try:
        from utils import (
            makeBytes, makeStr, download, verifyString, verifyStringList,
            getMimeType, audioInject, AjaxServer
        )
    except ImportError:
        # Final fallback - define locally
        from utils.helpers import makeBytes, makeStr, download, verifyString, verifyStringList, getMimeType, audioInject
        from utils.network import AjaxServer



#
# Constants
#

API_VERSION = 5
ADDON_VERSION = "0.0.9"  # This will be auto-updated by build_zip.sh
TICK_INTERVAL = 25
URL_TIMEOUT = 10
URL_UPGRADE = 'https://raw.githubusercontent.com/FooSoft/anki-connect/master/AnkiConnect.py'
NET_ADDRESS = os.getenv('ANKICONNECT_BIND_ADDRESS', '127.0.0.1')
NET_BACKLOG = 5
NET_PORT = 8765


#
# General helpers
#

if sys.version_info[0] < 3:
    import urllib2
    web = urllib2

    from PyQt4.QtCore import QTimer
    from PyQt4.QtGui import QMessageBox
else:
    unicode = str

    from urllib import request
    web = request

    # Try PyQt6 first (for newer Anki versions), then fall back to PyQt5
    try:
        from PyQt6.QtCore import QTimer
        from PyQt6.QtWidgets import QMessageBox
    except ImportError:
        from PyQt5.QtCore import QTimer
        from PyQt5.QtWidgets import QMessageBox


#
# Helpers
#

def webApi(*versions):
    """Decorator for marking API methods"""
    def decorator(func):
        method = lambda *args, **kwargs: func(*args, **kwargs)
        setattr(method, 'versions', versions)
        setattr(method, 'api', True)
        return method
    return decorator


def parseMultipartData(body, boundary):
    """
    Parse multipart/form-data request body
    
    Args:
        body: Request body as bytes
        boundary: Boundary string from Content-Type header
        
    Returns:
        dict: Parsed fields and files {'fields': {name: value}, 'files': {name: (filename, data)}}
    """
    parts = body.split(makeBytes('--' + boundary))
    fields = {}
    files = {}
    
    for part in parts:
        if len(part) <= 2 or part == makeBytes('--\r\n') or part == makeBytes('--'):
            continue
            
        # Split headers and content
        if makeBytes('\r\n\r\n') in part:
            header_part, content = part.split(makeBytes('\r\n\r\n'), 1)
        else:
            continue
        
        # Remove trailing \r\n from content
        if content.endswith(makeBytes('\r\n')):
            content = content[:-2]
        
        # Parse Content-Disposition header
        headers = header_part.split(makeBytes('\r\n'))
        content_disposition = None
        for header in headers:
            if header.lower().startswith(makeBytes('content-disposition:')):
                content_disposition = makeStr(header)
                break
        
        if not content_disposition:
            continue
        
        # Extract name and filename
        name_match = re.search(r'name="([^"]+)"', content_disposition)
        filename_match = re.search(r'filename="([^"]+)"', content_disposition)
        
        if name_match:
            name = name_match.group(1)
            if filename_match:
                # This is a file
                filename = filename_match.group(1)
                files[name] = (filename, content)
            else:
                # This is a regular field
                fields[name] = makeStr(content)
    
    return {'fields': fields, 'files': files}


#
# AnkiNoteParams
#

class AnkiNoteParams:
    def __init__(self, params):
        self.deckName = params.get('deckName')
        self.modelName = params.get('modelName')
        self.fields = params.get('fields', {})
        self.tags = params.get('tags', [])

        class Audio:
            def __init__(self, params):
                self.url = params.get('url')
                self.filename = params.get('filename')
                self.skipHash = params.get('skipHash')
                self.fields = params.get('fields', [])

            def validate(self):
                return (
                    verifyString(self.url) and
                    verifyString(self.filename) and os.path.dirname(self.filename) == '' and
                    verifyStringList(self.fields) and
                    (verifyString(self.skipHash) or self.skipHash is None)
                )

        audio = Audio(params.get('audio', {}))
        self.audio = audio if audio.validate() else None


    def validate(self):
        return (
            verifyString(self.deckName) and
            verifyString(self.modelName) and
            type(self.fields) == dict and verifyStringList(list(self.fields.keys())) and verifyStringList(list(self.fields.values())) and
            type(self.tags) == list and verifyStringList(self.tags)
        )


#
# AnkiBridge
#

class AnkiBridge:
    def __init__(self):
        pass
    
    def storeMediaFile(self, filename, data):
        self.deleteMediaFile(filename)
        self.media().writeData(filename, base64.b64decode(data))


    def retrieveMediaFile(self, filename):
        # based on writeData from anki/media.py
        filename = os.path.basename(filename)
        filename = normalize("NFC", filename)
        filename = self.media().stripIllegal(filename)

        path = os.path.join(self.media().dir(), filename)
        if os.path.exists(path):
            with open(path, 'rb') as file:
                return base64.b64encode(file.read()).decode('ascii')

        return False


    def deleteMediaFile(self, filename):
        self.media().syncDelete(filename)


    def addNote(self, params):
        collection = self.collection()
        if collection is None:
            return

        note = self.createNote(params)
        if note is None:
            return

        # Get the target deck
        deck = collection.decks.byName(params.deckName)
        if deck is None:
            return

        if params.audio is not None and len(params.audio.fields) > 0:
            data = download(params.audio.url)
            if data is not None:
                if params.audio.skipHash is None:
                    skip = False
                else:
                    m = hashlib.md5()
                    m.update(data)
                    skip = params.audio.skipHash == m.hexdigest()

                if not skip:
                    audioInject(note, params.audio.fields, params.audio.filename)
                    self.media().writeData(params.audio.filename, data)

        self.startEditing()
        collection.addNote(note)
        
        # Move the cards to the correct deck after note creation
        cardIds = [card.id for card in note.cards()]
        if cardIds and deck['id'] != collection.decks.get_current_id():
            self.changeDeck(cardIds, params.deckName)
        
        collection.autosave()
        self.stopEditing()

        return note.id


    def canAddNote(self, note):
        return bool(self.createNote(note))


    def createNote(self, params):
        collection = self.collection()
        if collection is None:
            return

        model = collection.models.byName(params.modelName)
        if model is None:
            return

        deck = collection.decks.byName(params.deckName)
        if deck is None:
            return

        note = anki.notes.Note(collection, model)
        note.tags = params.tags

        for name, value in params.fields.items():
            if name in note:
                note[name] = value

        # Check for duplicates - Anki checks the first field by default
        # Return the note even if it's a duplicate - let the caller decide
        return note

    def updateNoteFields(self, params):
        collection = self.collection()
        if collection is None:
            return

        note = collection.getNote(params['id'])
        if note is None:
            raise Exception("Failed to get note:{}".format(params['id']))
        for name, value in params['fields'].items():
            if name in note:
                note[name] = value
        note.flush()

    def addTags(self, notes, tags, add=True):
        self.startEditing()
        self.collection().tags.bulkAdd(notes, tags, add)
        self.stopEditing()


    def getTags(self):
        return self.collection().tags.all()


    def suspend(self, cards, suspend=True):
        for card in cards:
            isSuspended = self.isSuspended(card)
            if suspend and isSuspended:
                cards.remove(card)
            elif not suspend and not isSuspended:
                cards.remove(card)

        if cards:
            self.startEditing()
            if suspend:
                self.collection().sched.suspendCards(cards)
            else:
                self.collection().sched.unsuspendCards(cards)
            self.stopEditing()
            return True

        return False


    def areSuspended(self, cards):
        suspended = []
        for card in cards:
            card = self.collection().getCard(card)
            if card.queue == -1:
                suspended.append(True)
            else:
                suspended.append(False)
        return suspended


    def flagCard(self, cardId):
        """Flag a card with red flag (flag value 1)"""
        collection = self.collection()
        if collection is None:
            return False
        
        try:
            card = collection.getCard(cardId)
            if card is None:
                raise Exception(f"Card with ID '{cardId}' does not exist")
            
            self.startEditing()
            card.flags = 1  # Red flag
            card.flush()
            collection.autosave()
            self.stopEditing()
            return True
        except Exception as e:
            self.stopEditing()
            raise e


    def unflagCard(self, cardId):
        """Remove flag from a card (set flag value to 0)"""
        collection = self.collection()
        if collection is None:
            return False
        
        try:
            card = collection.getCard(cardId)
            if card is None:
                raise Exception(f"Card with ID '{cardId}' does not exist")
            
            self.startEditing()
            card.flags = 0  # No flag
            card.flush()
            collection.autosave()
            self.stopEditing()
            return True
        except Exception as e:
            self.stopEditing()
            raise e


    def isCardFlagged(self, cardId):
        """Check if a card is flagged"""
        collection = self.collection()
        if collection is None:
            return False
        
        try:
            card = collection.getCard(cardId)
            if card is None:
                raise Exception(f"Card with ID '{cardId}' does not exist")
            return card.flags > 0
        except Exception as e:
            raise e


    def areDue(self, cards):
        due = []
        for card in cards:
            if self.findCards('cid:%s is:new' % card):
                due.append(True)
                continue

            date, ivl = self.collection().db.all('select id/1000.0, ivl from revlog where cid = ?', card)[-1]
            if (ivl >= -1200):
                if self.findCards('cid:%s is:due' % card):
                    due.append(True)
                else:
                    due.append(False)
            else:
                if date - ivl <= time():
                    due.append(True)
                else:
                    due.append(False)

        return due


    def getIntervals(self, cards, complete=False):
        intervals = []
        for card in cards:
            if self.findCards('cid:%s is:new' % card):
                intervals.append(0)
                continue

            interval = self.collection().db.list('select ivl from revlog where cid = ?', card)
            if not complete:
                interval = interval[-1]
            intervals.append(interval)
        return intervals


    def startEditing(self):
        self.window().requireReset()


    def stopEditing(self):
        if self.collection() is not None:
            self.window().maybeReset()


    def window(self):
        return aqt.mw


    def reviewer(self):
        return self.window().reviewer


    def collection(self):
        return self.window().col


    def scheduler(self):
        return self.collection().sched


    def multi(self, actions):
        response = []
        for item in actions:
            response.append(AnkiConnect.handler(ac, item))
        return response


    def media(self):
        collection = self.collection()
        if collection is not None:
            return collection.media


    def modelNames(self):
        collection = self.collection()
        if collection is not None:
            return collection.models.allNames()


    def modelNamesAndIds(self):
        models = {}

        modelNames = self.modelNames()
        for model in modelNames:
            mid = self.collection().models.byName(model)['id']
            mid = int(mid)  # sometimes Anki stores the ID as a string
            models[model] = mid

        return models


    def modelNameFromId(self, modelId):
        collection = self.collection()
        if collection is not None:
            model = collection.models.get(modelId)
            if model is not None:
                return model['name']


    def modelFieldNames(self, modelName):
        collection = self.collection()
        if collection is not None:
            model = collection.models.byName(modelName)
            if model is not None:
                return [field['name'] for field in model['flds']]


    def modelFieldsOnTemplates(self, modelName):
        model = self.collection().models.byName(modelName)

        if model is not None:
            templates = {}
            for template in model['tmpls']:
                fields = []

                for side in ['qfmt', 'afmt']:
                    fieldsForSide = []

                    # based on _fieldsOnTemplate from aqt/clayout.py
                    matches = re.findall('{{[^#/}]+?}}', template[side])
                    for match in matches:
                        # remove braces and modifiers
                        match = re.sub(r'[{}]', '', match)
                        match = match.split(":")[-1]

                        # for the answer side, ignore fields present on the question side + the FrontSide field
                        if match == 'FrontSide' or side == 'afmt' and match in fields[0]:
                            continue
                        fieldsForSide.append(match)


                    fields.append(fieldsForSide)

                templates[template['name']] = fields

            return templates




    def getDeckConfig(self, deck):
        if not deck in self.deckNames():
            return False

        did = self.collection().decks.id(deck)
        return self.collection().decks.confForDid(did)


    def saveDeckConfig(self, config):
        configId = str(config['id'])
        if not configId in self.collection().decks.dconf:
            return False

        mod = anki.utils.intTime()
        usn = self.collection().usn()

        config['mod'] = mod
        config['usn'] = usn

        self.collection().decks.dconf[configId] = config
        self.collection().decks.changed = True
        return True


    def setDeckConfigId(self, decks, configId):
        for deck in decks:
            if not deck in self.deckNames():
                return False

        if not str(configId) in self.collection().decks.dconf:
            return False

        for deck in decks:
            did = str(self.collection().decks.id(deck))
            aqt.mw.col.decks.decks[did]['conf'] = configId

        return True


    def cloneDeckConfigId(self, name, cloneFrom=1):
        if not str(cloneFrom) in self.collection().decks.dconf:
            return False

        cloneFrom = self.collection().decks.getConf(cloneFrom)
        return self.collection().decks.confId(name, cloneFrom)


    def removeDeckConfigId(self, configId):
        if configId == 1 or not str(configId) in self.collection().decks.dconf:
            return False

        self.collection().decks.remConf(configId)
        return True


    def deckNames(self):
        collection = self.collection()
        if collection is not None:
            return collection.decks.allNames()


    def deckNamesAndIds(self):
        decks = {}

        deckNames = self.deckNames()
        for deck in deckNames:
            did = self.collection().decks.id(deck)
            decks[deck] = did

        return decks


    def deckNameFromId(self, deckId):
        collection = self.collection()
        if collection is not None:
            deck = collection.decks.get(deckId)
            if deck is not None:
                return deck['name']


    def findNotes(self, query=None):
        if query is not None:
            return self.collection().findNotes(query)
        else:
            return []


    def findCards(self, query=None):
        if query is not None:
            return self.collection().findCards(query)
        else:
            return []

    def cardsInfo(self,cards):
        result = []
        for cid in cards:
            try:
                card = self.collection().getCard(cid)
                model = card.model()
                note = card.note()
                fields = {}
                for info in model['flds']:
                    order = info['ord']
                    name = info['name']
                    fields[name] = {'value': note.fields[order], 'order': order}
                
                # Get question and answer with version compatibility
                try:
                    # Try new Anki 2.1.50+ API
                    question = card.question()
                    answer = card.answer()
                except (AttributeError, TypeError):
                    # Fall back to older API
                    try:
                        qa = card._getQA()
                        question = qa['q']
                        answer = qa['a']
                    except:
                        question = ""
                        answer = ""
            
                result.append({
                    'cardId': card.id,
                    'fields': fields,
                    'fieldOrder': card.ord,
                    'question': question,
                    'answer': answer,
                    'modelName': model['name'],
                    'deckName': self.deckNameFromId(card.did),
                    'css': model['css'],
                    'factor': card.factor, 
                    #This factor is 10 times the ease percentage, 
                    # so an ease of 310% would be reported as 3100
                    'interval': card.ivl,
                    'note': card.nid,
                    'flagged': card.flags > 0
                })
            except TypeError as e:
                # Anki will give a TypeError if the card ID does not exist.
                # Best behavior is probably to add an "empty card" to the
                # returned result, so that the items of the input and return
                # lists correspond.
                result.append({})

        return result

    def notesInfo(self,notes):
        result = []
        for nid in notes:
            try:
                note = self.collection().getNote(nid)
                model = note.model()

                fields = {}
                for info in model['flds']:
                    order = info['ord']
                    name = info['name']
                    fields[name] = {'value': note.fields[order], 'order': order}
            
                result.append({
                    'noteId': note.id,
                    'tags' : note.tags,
                    'fields': fields,
                    'modelName': model['name'],
                    'cards': self.collection().db.list(
                        "select id from cards where nid = ? order by ord", note.id)
                })
            except TypeError as e:
                # Anki will give a TypeError if the note ID does not exist.
                # Best behavior is probably to add an "empty card" to the
                # returned result, so that the items of the input and return
                # lists correspond.
                result.append({})
        return result


    def getDecks(self, cards):
        decks = {}
        for card in cards:
            did = self.collection().db.scalar('select did from cards where id = ?', card)
            deck = self.collection().decks.get(did)['name']

            if deck in decks:
                decks[deck].append(card)
            else:
                decks[deck] = [card]

        return decks


    def changeDeck(self, cards, deck):
        self.startEditing()

        did = self.collection().decks.id(deck)
        mod = anki.utils.intTime()
        usn = self.collection().usn()

        # normal cards
        scids = anki.utils.ids2str(cards)
        # remove any cards from filtered deck first
        self.collection().sched.remFromDyn(cards)

        # then move into new deck
        self.collection().db.execute('update cards set usn=?, mod=?, did=? where id in ' + scids, usn, mod, did)
        self.stopEditing()


    def deleteDecks(self, decks, cardsToo=False):
        self.startEditing()
        for deck in decks:
            did = self.collection().decks.id(deck)
            self.collection().decks.rem(did, cardsToo)
        self.stopEditing()


    def cardsToNotes(self, cards):
        return self.collection().db.list('select distinct nid from cards where id in ' + anki.utils.ids2str(cards))


    def guiBrowse(self, query=None):
        browser = aqt.dialogs.open('Browser', self.window())
        browser.activateWindow()

        if query is not None:
            browser.form.searchEdit.lineEdit().setText(query)
            if hasattr(browser, 'onSearch'):
                browser.onSearch()
            else:
                browser.onSearchActivated()

        return browser.model.cards


    def guiAddCards(self):
        addCards = aqt.dialogs.open('AddCards', self.window())
        addCards.activateWindow()


    def guiReviewActive(self):
        return self.reviewer().card is not None and self.window().state == 'review'


    def guiCurrentCard(self):
        if not self.guiReviewActive():
            return

        reviewer = self.reviewer()
        card = reviewer.card
        model = card.model()
        note = card.note()

        fields = {}
        for info in model['flds']:
            order = info['ord']
            name = info['name']
            fields[name] = {'value': note.fields[order], 'order': order}

        # Get question and answer with version compatibility
        try:
            # Try new Anki 2.1.50+ API
            question = card.question()
            answer = card.answer()
        except (AttributeError, TypeError):
            # Fall back to older API
            try:
                qa = card._getQA()
                question = qa['q']
                answer = qa['a']
            except:
                question = ""
                answer = ""

        if card is not None:
            return {
                'cardId': card.id,
                'fields': fields,
                'fieldOrder': card.ord,
                'question': question,
                'answer': answer,
                'buttons': [b[0] for b in reviewer._answerButtonList()],
                'modelName': model['name'],
                'deckName': self.deckNameFromId(card.did),
                'css': model['css'],
                'flagged': card.flags > 0
            }


    def guiStartCardTimer(self):
        if not self.guiReviewActive():
            return False

        card = self.reviewer().card

        if card is not None:
            card.startTimer()
            return True
        else:
            return False

    def guiShowQuestion(self):
        if self.guiReviewActive():
            self.reviewer()._showQuestion()
            return True
        else:
            return False


    def guiShowAnswer(self):
        if self.guiReviewActive():
            self.window().reviewer._showAnswer()
            return True
        else:
            return False


    def guiAnswerCard(self, ease):
        if not self.guiReviewActive():
            return False

        reviewer = self.reviewer()
        if reviewer.state != 'answer':
            return False
        if ease <= 0 or ease > self.scheduler().answerButtons(reviewer.card):
            return False

        reviewer._answerCard(ease)
        return True


    def guiDeckOverview(self, name):
        collection = self.collection()
        if collection is not None:
            deck = collection.decks.byName(name)
            if deck is not None:
                collection.decks.select(deck['id'])
                self.window().onOverview()
                return True

        return False


    def guiDeckBrowser(self):
        self.window().moveToState('deckBrowser')


    def guiDeckReview(self, name):
        if self.guiDeckOverview(name):
            self.window().moveToState('review')
            return True
        else:
            return False

    def guiExitAnki(self):
        timer = QTimer()
        def exitAnki():
            timer.stop()
            self.window().close()
        timer.timeout.connect(exitAnki)
        timer.start(1000) # 1s should be enough to allow the response to be sent.

    def addAudioNote(self, params, audioFile, allowDuplicate=True):
        """
        Add a note with audio file from URL
        
        Args:
            params: Note parameters (deckName, modelName, fields, tags)
            audioFile: URL to MP3 file (e.g., Digital Ocean Spaces URL)
            allowDuplicate: Allow duplicate first field (default: True)
        
        Returns:
            Note ID on success
        """
        try:
            collection = self.collection()
            if collection is None:
                raise Exception("Anki collection not available - is Anki running?")
            
            # Validate model exists
            model_name = params.get('modelName')
            model = collection.models.byName(model_name)
            if model is None:
                available_models = collection.models.allNames()
                raise Exception(f"Model '{model_name}' not found. Available models: {', '.join(available_models)}")
            
            # Check if model has Audio1 field
            model_fields = [field['name'] for field in model['flds']]
            if 'Audio1' not in model_fields:
                raise Exception(f"Model '{model_name}' must have an 'Audio1' field. Current fields: {', '.join(model_fields)}")
            
            # Validate deck exists
            deck_name = params.get('deckName')
            deck = collection.decks.byName(deck_name)
            if deck is None:
                available_decks = collection.decks.allNames()
                raise Exception(f"Deck '{deck_name}' not found. Available decks: {', '.join(available_decks[:10])}...")
            
            # Validate audioFile
            if not audioFile or not verifyString(audioFile):
                raise Exception("audioFile is required and must be a valid URL string")
            
            # Download audio file from URL
            try:
                audio_data = download(audioFile)
                if audio_data is None:
                    raise Exception(f"Failed to download audio from URL: {audioFile}")
            except Exception as e:
                raise Exception(f"Failed to download audio from URL: {str(e)}")
            
            # Validate that we got audio data
            if not audio_data or len(audio_data) == 0:
                raise Exception("Downloaded file is empty")
            
            # Generate filename from URL
            import urllib.parse
            parsed_url = urllib.parse.urlparse(audioFile)
            url_filename = os.path.basename(parsed_url.path)
            
            if url_filename and '.' in url_filename:
                # Use filename from URL with unique timestamp
                timestamp = int(time())
                name, ext = os.path.splitext(url_filename)
                audioFilename = f"{name}_{timestamp}{ext}"
            else:
                # Generate completely new filename
                timestamp = int(time())
                url_hash = hashlib.md5(audioFile.encode('utf-8')).hexdigest()[:8]
                audioFilename = f"audio_{timestamp}_{url_hash}.mp3"
            
            # Ensure filename has no directory components
            audioFilename = os.path.basename(audioFilename)
            
            # Store audio file in media folder
            try:
                self.media().writeData(audioFilename, audio_data)
            except Exception as e:
                raise Exception(f"Failed to write audio file to media folder: {str(e)}")
            
            # Add audio reference to Audio1 field
            if 'Audio1' not in params['fields']:
                params['fields']['Audio1'] = ''
            params['fields']['Audio1'] += u'[sound:{}]'.format(audioFilename)
            
            # Create the note
            note_params = AnkiNoteParams(params)
            if not note_params.validate():
                raise Exception("Note parameters validation failed. Check deckName, modelName, fields, and tags are all valid strings.")
            
            # Create note object
            model = collection.models.byName(model_name)
            note = anki.notes.Note(collection, model)
            note.tags = params.get('tags', [])
            
            for name, value in params['fields'].items():
                if name in note:
                    note[name] = value
            
            # Check for duplicates if not allowed
            if not allowDuplicate and note.dupeOrEmpty():
                raise Exception(f"Duplicate note detected. First field already exists.")
            
            self.startEditing()
            collection.addNote(note)
            
            # Move the cards to the correct deck after note creation
            cardIds = [card.id for card in note.cards()]
            if cardIds and deck['id'] != collection.decks.get_current_id():
                self.changeDeck(cardIds, deck_name)
            
            collection.autosave()
            self.stopEditing()
            
            return note.id
            
        except Exception as e:
            # Re-raise with context
            raise Exception(f"addAudioNote error: {str(e)}")

    def importPackage(self, packageUrl, parentDeck=None, allowDuplicates=False):
        """
        Import an Anki package (.apkg) from a URL using the modern backend API
        
        Args:
            packageUrl: URL to .apkg file
            parentDeck: Optional parent deck name - cards will be moved to this deck
            allowDuplicates: If True, attempt to update duplicate notes; if False (default), skip duplicates
        
        Returns:
            dict with import success status and log
        """
        tmp_path = None
        
        try:
            collection = self.collection()
            if collection is None:
                raise Exception("Collection not available")
            
            # If parentDeck is specified, ensure it exists
            if parentDeck:
                # Create the parent deck if it doesn't exist
                parent_deck = collection.decks.byName(parentDeck)
                if parent_deck is None:
                    collection.decks.id(parentDeck)  # This creates the deck
                    parent_deck = collection.decks.byName(parentDeck)
            
            # Download file
            try:
                if sys.version_info[0] < 3:
                    import urllib2
                    req = urllib2.Request(packageUrl)
                    resp = urllib2.urlopen(req, timeout=60)
                else:
                    from urllib import request
                    req = request.Request(packageUrl)
                    req.add_header('User-Agent', 'AnkiConnect')
                    resp = request.urlopen(req, timeout=60)
                
                if resp.code != 200:
                    raise Exception(f"HTTP {resp.code}: Server returned error")
                
                package_data = resp.read()
                if not package_data or len(package_data) == 0:
                    raise Exception("Downloaded data is empty")
                
                if not package_data.startswith(b'PK\x03\x04'):
                    raise Exception("Downloaded data is not a valid zip/apkg file")
                    
            except Exception as e:
                raise Exception(f"Download failed: {str(e)}")
            
            # Write to temp file
            try:
                with tempfile.NamedTemporaryFile(suffix='.apkg', delete=False) as tmp_file:
                    tmp_file.write(package_data)
                    tmp_file.flush()
                    os.fsync(tmp_file.fileno())
                    tmp_path = tmp_file.name
                
                if not os.path.exists(tmp_path) or os.path.getsize(tmp_path) == 0:
                    raise Exception("Failed to create temporary file")
                    
            except Exception as e:
                if tmp_path and os.path.exists(tmp_path):
                    try:
                        os.unlink(tmp_path)
                    except:
                        pass
                raise Exception(f"Failed to write temporary file: {str(e)}")
            
            # Import using the modern backend API
            try:
                # Import the protobuf classes
                from anki.collection import ImportAnkiPackageRequest, ImportAnkiPackageOptions
                from anki import import_export_pb2
                
                # Get deck names and card IDs before import to track what was imported
                decks_before = set(collection.decks.allNames())
                cards_before = set(collection.db.list('select id from cards'))
                
                # Create import options
                options = ImportAnkiPackageOptions()
                options.merge_notetypes = True  # Merge note types if they exist
                options.with_scheduling = True   # Include scheduling information
                options.with_deck_configs = True  # Include deck configurations
                
                # Configure duplicate handling using update_notes field
                if allowDuplicates:
                    # ALWAYS = 1: Always update existing notes if duplicates found
                    options.update_notes = import_export_pb2.ImportAnkiPackageUpdateCondition.IMPORT_ANKI_PACKAGE_UPDATE_CONDITION_ALWAYS
                else:
                    # IF_NEWER = 0: Skip duplicates (default behavior)
                    options.update_notes = import_export_pb2.ImportAnkiPackageUpdateCondition.IMPORT_ANKI_PACKAGE_UPDATE_CONDITION_IF_NEWER
                
                # Create the import request
                request = ImportAnkiPackageRequest()
                request.package_path = tmp_path
                request.options.CopyFrom(options)
                
                # Perform the import using the backend
                result = collection.import_anki_package(request)
                
                # If parentDeck specified, move cards to properly named subdeck
                if parentDeck:
                    # Extract deck name from URL as fallback
                    # URL format: ${userId}_${uuidv4()}_${sanitizedFilename}.apkg
                    extracted_name = None
                    try:
                        import urllib.parse
                        parsed_url = urllib.parse.urlparse(packageUrl)
                        url_filename = os.path.basename(parsed_url.path)
                        
                        # Remove .apkg extension
                        if url_filename.endswith('.apkg'):
                            url_filename = url_filename[:-5]
                        
                        # Split by underscore and skip first two parts (userId and uuid)
                        parts = url_filename.split('_')
                        if len(parts) >= 3:
                            # Join remaining parts (in case sanitized filename has underscores)
                            extracted_name = '_'.join(parts[2:])
                    except:
                        extracted_name = None
                    
                    # Get new cards that were imported
                    cards_after = set(collection.db.list('select id from cards'))
                    new_card_ids = list(cards_after - cards_before)
                    
                    if new_card_ids:
                        # Get new decks that were created by the import
                        decks_after = set(collection.decks.allNames())
                        new_decks = decks_after - decks_before
                        
                        # Determine the subdeck name
                        subdeck_name = extracted_name if extracted_name else "imported"
                        
                        # If there are imported decks, check their names
                        if new_decks:
                            first_deck = list(new_decks)[0]
                            # Use extracted name if deck is "Default", otherwise use the deck's name
                            if first_deck.lower() != "default" and not extracted_name:
                                subdeck_name = first_deck
                            elif extracted_name:
                                subdeck_name = extracted_name
                            else:
                                subdeck_name = first_deck
                        
                        # Create the properly named subdeck: parentDeck::subdeck_name
                        target_deck_name = f"{parentDeck}::{subdeck_name}"
                        
                        # Create the deck (this will create parent hierarchy if needed)
                        collection.decks.id(target_deck_name)
                        
                        # Move all imported cards to the target subdeck
                        self.startEditing()
                        self.changeDeck(new_card_ids, target_deck_name)
                        self.stopEditing()
                        
                        # Delete the temporary imported decks (cards are already moved)
                        for temp_deck_name in new_decks:
                            try:
                                temp_deck = collection.decks.byName(temp_deck_name)
                                if temp_deck:
                                    collection.decks.rem(temp_deck['id'], cardsToo=False)
                            except:
                                pass
                        
                        # Save all changes
                        collection.save()
                
                # Build log message from result
                log_parts = []
                if result.log.new:
                    log_parts.append(f"Added {len(result.log.new)} notes")
                if result.log.updated:
                    log_parts.append(f"Updated {len(result.log.updated)} notes")
                if result.log.duplicate:
                    log_parts.append(f"Skipped {len(result.log.duplicate)} duplicates")
                
                if parentDeck:
                    log_parts.append(f"Imported under '{parentDeck}'")
                
                log = ", ".join(log_parts) if log_parts else "Import completed"
                
                return {
                    'success': True,
                    'log': log,
                    'notes_added': len(result.log.new),
                    'notes_updated': len(result.log.updated),
                    'notes_duplicate': len(result.log.duplicate)
                }
                
            except Exception as e:
                # If backend import fails, provide helpful error
                raise Exception(f"Import failed: {str(e)}")
                    
        except Exception as e:
            error_msg = str(e)
            if "Invalid file" in error_msg:
                raise Exception("Invalid .apkg file. The file may be corrupted.")
            else:
                raise Exception(f"Import error: {error_msg}")
        finally:
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except:
                    pass



#
# AnkiConnect
#

class AnkiConnect:
    def __init__(self):
        self.anki = AnkiBridge()
        self.server = AjaxServer(self.handler)

        try:
            self.server.listen()

            self.timer = QTimer()
            self.timer.timeout.connect(self.advance)
            self.timer.start(TICK_INTERVAL)
        except:
            QMessageBox.critical(
                self.anki.window(),
                'AnkiConnect',
                'Failed to listen on port {}.\nMake sure it is available and is not in use.'.format(NET_PORT)
            )


    def advance(self):
        self.server.advance()


    def handler(self, request):
        name = request.get('action', '')
        version = request.get('version', 4)
        params = request.get('params', {})
        reply = {'result': None, 'error': None}

        try:
            method = None

            for methodName, methodInst in inspect.getmembers(self, predicate=inspect.ismethod):
                apiVersionLast = 0
                apiNameLast = None

                if getattr(methodInst, 'api', False):
                    for apiVersion, apiName in getattr(methodInst, 'versions', []):
                        if apiVersionLast < apiVersion <= version:
                            apiVersionLast = apiVersion
                            apiNameLast = apiName

                    if apiNameLast is None and apiVersionLast == 0:
                        apiNameLast = methodName

                    if apiNameLast is not None and apiNameLast == name:
                        method = methodInst
                        break

            if method is None:
                raise Exception('unsupported action')
            else:
                reply['result'] = methodInst(**params)
        except Exception as e:
            reply['error'] = str(e)

        if version > 4:
            return reply
        else:
            return reply['result']


    @webApi()
    def multi(self, actions):
        return self.anki.multi(actions)


    @webApi()
    def storeMediaFile(self, filename, data):
        return self.anki.storeMediaFile(filename, data)


    @webApi()
    def retrieveMediaFile(self, filename):
        return self.anki.retrieveMediaFile(filename)


    @webApi()
    def deleteMediaFile(self, filename):
        return self.anki.deleteMediaFile(filename)


    @webApi()
    def deckNames(self):
        return self.anki.deckNames()


    @webApi()
    def deckNamesAndIds(self):
        return self.anki.deckNamesAndIds()


    @webApi()
    def modelNames(self):
        return self.anki.modelNames()


    @webApi()
    def modelNamesAndIds(self):
        return self.anki.modelNamesAndIds()


    @webApi()
    def modelFieldNames(self, modelName):
        return self.anki.modelFieldNames(modelName)


    @webApi()
    def modelFieldsOnTemplates(self, modelName):
        return self.anki.modelFieldsOnTemplates(modelName)


    @webApi()
    def getDeckConfig(self, deck):
        return self.anki.getDeckConfig(deck)


    @webApi()
    def saveDeckConfig(self, config):
        return self.anki.saveDeckConfig(config)


    @webApi()
    def setDeckConfigId(self, decks, configId):
        return self.anki.setDeckConfigId(decks, configId)


    @webApi()
    def cloneDeckConfigId(self, name, cloneFrom=1):
        return self.anki.cloneDeckConfigId(name, cloneFrom)


    @webApi()
    def removeDeckConfigId(self, configId):
        return self.anki.removeDeckConfigId(configId)


    @webApi()
    def addNote(self, note):
        params = AnkiNoteParams(note)
        if not params.validate():
            raise Exception("Note parameters validation failed")
        
        result = self.anki.addNote(params)
        if result is None:
            raise Exception("Failed to create note - no note ID returned")
        return result


    @webApi()
    def addNotes(self, notes):
        results = []
        for note in notes:
            params = AnkiNoteParams(note)
            if params.validate():
                results.append(self.anki.addNote(params))
            else:
                results.append(None)

        return results

    @webApi()
    def updateNoteFields(self, note):
        return self.anki.updateNoteFields(note)

    @webApi()
    def canAddNotes(self, notes):
        results = []
        for note in notes:
            params = AnkiNoteParams(note)
            results.append(params.validate() and self.anki.canAddNote(params))

        return results


    @webApi()
    def addTags(self, notes, tags, add=True):
        return self.anki.addTags(notes, tags, add)


    @webApi()
    def removeTags(self, notes, tags):
        return self.anki.addTags(notes, tags, False)


    @webApi()
    def getTags(self):
        return self.anki.getTags()


    @webApi()
    def suspend(self, cards, suspend=True):
        return self.anki.suspend(cards, suspend)


    @webApi()
    def unsuspend(self, cards):
        return self.anki.suspend(cards, False)


    @webApi()
    def areSuspended(self, cards):
        return self.anki.areSuspended(cards)


    @webApi()
    def areDue(self, cards):
        return self.anki.areDue(cards)


    @webApi()
    def getIntervals(self, cards, complete=False):
        return self.anki.getIntervals(cards, complete)


    @webApi()
    def upgrade(self):
        response = QMessageBox.question(
            self.anki.window(),
            'AnkiConnect',
            'Upgrade to the latest version?',
            QMessageBox.Yes | QMessageBox.No
        )

        if response == QMessageBox.Yes:
            data = download(URL_UPGRADE)
            if data is None:
                QMessageBox.critical(self.anki.window(), 'AnkiConnect', 'Failed to download latest version.')
            else:
                path = os.path.splitext(__file__)[0] + '.py'
                with open(path, 'w') as fp:
                    fp.write(makeStr(data))
                QMessageBox.information(self.anki.window(), 'AnkiConnect', 'Upgraded to the latest version, please restart Anki.')
                return True

        return False


    @webApi()
    def version(self):
        return API_VERSION
    
    @webApi()
    def addonVersion(self):
        """Get the add-on version"""
        return ADDON_VERSION
    
    @webApi()
    def debugInfo(self):
        """Debug endpoint to check what methods are available"""
        import sys
        info = {
            'apiVersion': API_VERSION,
            'ankiConnectFile': __file__,
            'studyManagerFile': None,
            'availableMethods': [],
            'answerCardSignature': None
        }
        
        # Get study_manager file location
        try:
            import study_manager
            info['studyManagerFile'] = study_manager.__file__
        except:
            pass
        
        # Check answerCard method signature
        try:
            import inspect as insp
            sig = insp.signature(self.answerCard)
            info['answerCardSignature'] = str(sig)
            info['answerCardParameters'] = list(sig.parameters.keys())
        except Exception as e:
            info['answerCardSignature'] = f"Error: {str(e)}"
        
        # List all @webApi methods
        for methodName, methodInst in inspect.getmembers(self, predicate=inspect.ismethod):
            if getattr(methodInst, 'api', False):
                info['availableMethods'].append(methodName)
        
        return info


    @webApi()
    def findNotes(self, query=None):
        return self.anki.findNotes(query)


    @webApi()
    def findCards(self, query=None):
        return self.anki.findCards(query)


    @webApi()
    def getDecks(self, cards):
        return self.anki.getDecks(cards)


    @webApi()
    def changeDeck(self, cards, deck):
        return self.anki.changeDeck(cards, deck)


    @webApi()
    def deleteDecks(self, decks, cardsToo=False):
        return self.anki.deleteDecks(decks, cardsToo)


    @webApi()
    def cardsToNotes(self, cards):
        return self.anki.cardsToNotes(cards)


    @webApi()
    def guiBrowse(self, query=None):
        return self.anki.guiBrowse(query)


    @webApi()
    def guiAddCards(self):
        return self.anki.guiAddCards()


    @webApi()
    def guiCurrentCard(self):
        return self.anki.guiCurrentCard()


    @webApi()
    def guiStartCardTimer(self):
        return self.anki.guiStartCardTimer()


    @webApi()
    def guiAnswerCard(self, ease):
        return self.anki.guiAnswerCard(ease)


    @webApi()
    def guiShowQuestion(self):
        return self.anki.guiShowQuestion()


    @webApi()
    def guiShowAnswer(self):
        return self.anki.guiShowAnswer()


    @webApi()
    def guiDeckOverview(self, name):
        return self.anki.guiDeckOverview(name)


    @webApi()
    def guiDeckBrowser(self):
        return self.anki.guiDeckBrowser()


    @webApi()
    def guiDeckReview(self, name):
        return self.anki.guiDeckReview(name)


    @webApi()
    def guiExitAnki(self):
        return self.anki.guiExitAnki()

    @webApi()
    def addAudioNote(self, note, audioFile, allowDuplicate=True):
        """
        Add a note with audio file from URL
        
        Args:
            note: Note parameters (deckName, modelName, fields, tags)
            audioFile: URL to MP3 file (e.g., Digital Ocean Spaces URL)
            allowDuplicate: Allow duplicate notes (default: True)
        
        Returns:
            Note ID on success
        """
        return self.anki.addAudioNote(note, audioFile, allowDuplicate)

    @webApi()
    def importPackage(self, packageUrl, parentDeck=None, allowDuplicates=False):
        """
        Import an Anki package (.apkg) from a URL
        
        Args:
            packageUrl: URL to .apkg file (e.g., Digital Ocean Spaces URL)
            parentDeck: Optional parent deck name to import under (preserves original deck structure)
            allowDuplicates: If True, import duplicate notes; if False (default), skip duplicates
        
        Returns:
            dict with import statistics including success status, notes added/updated/duplicated, and deck name
        """
        return self.anki.importPackage(packageUrl, parentDeck, allowDuplicates)

    @webApi()
    def cardsInfo(self, cards):
        return self.anki.cardsInfo(cards)

    @webApi()
    def notesInfo(self, notes):
        return self.anki.notesInfo(notes)

    # Note/Model Management - Simple current profile usage
    @webApi()
    def createModel(self, modelName, fields, templates, css=""):
        return NoteManager(self.anki).createModel(modelName, fields, templates, css)

    @webApi()
    def updateModel(self, modelId, modelName=None, fields=None, templates=None, css=None):
        return NoteManager(self.anki).updateModel(modelId, modelName, fields, templates, css)

    @webApi()
    def deleteModel(self, modelId):
        return NoteManager(self.anki).deleteModel(modelId)

    @webApi()
    def createDeck(self, deckName):
        return NoteManager(self.anki).createDeck(deckName)

    @webApi()
    def getModelInfo(self, modelId):
        return NoteManager(self.anki).getModelInfo(modelId)

    @webApi()
    def getDeckInfo(self, deckName, includeTimeStats=True, period="allTime", wantSingleDeckStats=False):
        return NoteManager(self.anki).getDeckInfo(deckName, includeTimeStats, period, wantSingleDeckStats)

    @webApi()
    def deleteDeck(self, deckName, deleteCards=False):
        return NoteManager(self.anki).deleteDeck(deckName, deleteCards)

    @webApi()
    def renameDeck(self, oldName, newName):
        return NoteManager(self.anki).renameDeck(oldName, newName)

    # Study Management - Direct usage  
    @webApi()
    def getNextReviewCard(self, deckName=None):
        return StudyManager(self.anki).getNextReviewCard(deckName)

    @webApi()
    def answerCard(self, cardId, ease, timeTakenSeconds=None):
        return StudyManager(self.anki).answerCard(cardId, ease, timeTakenSeconds)

    @webApi()
    def resetCard(self, cardId):
        return StudyManager(self.anki).resetCard(cardId)

    @webApi()
    def forgetCard(self, cardId):
        return StudyManager(self.anki).forgetCard(cardId)

    @webApi()
    def getDueCards(self, deckName=None, limit=10):
        return StudyManager(self.anki).getDueCards(deckName, limit)

    @webApi()
    def getNewCards(self, deckName=None, limit=10):
        return StudyManager(self.anki).getNewCards(deckName, limit)

    @webApi()
    def getStudyStats(self, deckName=None):
        return StudyManager(self.anki).getStudyStats(deckName)

    @webApi()
    def getDeckTimeStats(self, deckName=None, period="allTime"):
        return StudyManager(self.anki).getDeckTimeStats(deckName, period)

    @webApi()
    def flagCard(self, cardId):
        """
        Flag a card with red flag
        
        Args:
            cardId (int): ID of the card to flag
            
        Returns:
            bool: True if successful
        """
        return self.anki.flagCard(cardId)

    @webApi()
    def unflagCard(self, cardId):
        """
        Remove flag from a card
        
        Args:
            cardId (int): ID of the card to unflag
            
        Returns:
            bool: True if successful
        """
        return self.anki.unflagCard(cardId)

    @webApi()
    def isCardFlagged(self, cardId):
        """
        Check if a card is flagged
        
        Args:
            cardId (int): ID of the card to check
            
        Returns:
            bool: True if card is flagged
        """
        return self.anki.isCardFlagged(cardId)

    @webApi()
    def setDeckStudyOptions(self, deckName, newCardsPerDay=None, reviewsPerDay=None):
        """
        Set study options for a deck (convenience wrapper for getDeckConfig/saveDeckConfig)
        
        Args:
            deckName (str): Name of the deck to configure
            newCardsPerDay (int, optional): Maximum new cards to study per day
            reviewsPerDay (int, optional): Maximum review cards per day
            
        Returns:
            dict: Updated configuration with the new settings
        """
        return StudyManager(self.anki).setDeckStudyOptions(deckName, newCardsPerDay, reviewsPerDay)

    @webApi()
    def extendNewCardLimit(self, deckName, additionalCards):
        """
        Extend today's new card limit for a specific deck
        
        Args:
            deckName (str): Name of the deck
            additionalCards (int): Number of additional new cards to allow today
            
        Returns:
            dict: Information about the extended limit
        """
        return StudyManager(self.anki).extendNewCardLimit(deckName, additionalCards)

    @webApi()
    def enableStudyForgotten(self, deckName, days=1, filteredDeckName=None):
        """
        Create a filtered deck for studying cards that were forgotten (answered "Again") in the last X days.
        Matches Anki's native "Review forgotten cards" custom study option.
        
        Args:
            deckName (str): Name of the source deck
            days (int): Look back this many days for forgotten cards (default: 1 = today only)
            filteredDeckName (str, optional): Custom name for the filtered deck. If not provided, auto-generates name.
            
        Returns:
            dict: Information about the created filtered deck
        """
        return StudyManager(self.anki).enableStudyForgotten(deckName, days, filteredDeckName)

    @webApi()
    def createCustomStudy(self, deckName, newCardsPerDay=None, reviewsPerDay=None, 
                         studyForgottenToday=False, extendNewLimit=None):
        """
        Combined API for creating a custom study session with various options
        
        Args:
            deckName (str): Name of the deck to configure
            newCardsPerDay (int, optional): Set new cards per day limit
            reviewsPerDay (int, optional): Set reviews per day limit
            studyForgottenToday (bool): Create filtered deck for forgotten cards today
            extendNewLimit (int, optional): Extend today's new card limit by this many cards
            
        Returns:
            dict: Results of all requested operations
        """
        return StudyManager(self.anki).createCustomStudy(
            deckName, newCardsPerDay, reviewsPerDay, studyForgottenToday, extendNewLimit
        )
    
    @webApi()
    def getDeckReviewsByDay(self, deckName, days=14):
        """
        Get the number of reviews completed per day for the last N days.
        Uses the same approach as Anki's built-in statistics calendar.
        
        Args:
            deckName (str): Name of the deck
            days (int): Number of days to look back (default: 14)
            
        Returns:
            dict: Daily review statistics with breakdown by card type (learning, review, relearn, filtered)
        """
        return StudyManager(self.anki).getDeckReviewsByDay(deckName, days)

#
#   Entry
#

ac = AnkiConnect()
