# Copyright (C) 2025
# Study and Review Management for AnkiConnect
#
# This module handles card studying, reviewing, and scheduling
# functionality for AnkiConnect.

import anki
import anki.utils

class StudyManager:
    """Manages card studying and review functionality"""
    
    def __init__(self, bridge):
        self.bridge = bridge
    
    def collection(self):
        """Get the current Anki collection"""
        return self.bridge.collection()
    
    def startEditing(self):
        """Start editing session"""
        self.bridge.startEditing()
    
    def stopEditing(self):
        """Stop editing session"""
        self.bridge.stopEditing()

    def getNextReviewCard(self, deckName=None):
        """
        Get the next card due for review from a specific deck or all decks
        
        Args:
            deckName (str, optional): Name of the deck to get cards from
            
        Returns:
            dict: Card information if available, None if no cards due
        """
        collection = self.collection()
        if collection is None:
            return None
        
        # If deck specified, set it as current
        if deckName:
            deck = collection.decks.byName(deckName)
            if deck is None:
                raise Exception(f"Deck '{deckName}' does not exist")
            collection.decks.select(deck['id'])
        
        # Get next card from scheduler
        card = collection.sched.getCard()
        if card is None:
            return None
            
        # Get card information
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
        
        return {
            'cardId': card.id,
            'fields': fields,
            'fieldOrder': card.ord,
            'question': question,
            'answer': answer,
            'modelName': model['name'],
            'deckName': self.bridge.deckNameFromId(card.did),
            'css': model['css'],
            'factor': card.factor,
            'interval': card.ivl,
            'due': card.due,
            'queue': card.queue,
            'type': card.type,
            'noteId': card.nid,
            'buttons': self._getAnswerButtons(card)
        }
    
    def answerCard(self, cardId, ease):
        """
        Answer a card with the specified ease
        
        Args:
            cardId (int): ID of the card to answer
            ease (int): Ease/difficulty rating (1=Again, 2=Hard, 3=Good, 4=Easy)
            
        Returns:
            bool: True if successful
        """
        collection = self.collection()
        if collection is None:
            return False
            
        try:
            card = collection.getCard(cardId)
            if card is None:
                raise Exception(f"Card with ID '{cardId}' does not exist")
            
            # Validate ease
            if ease < 1 or ease > 4:
                raise Exception(f"Invalid ease value '{ease}'. Must be between 1-4")
            
            self.startEditing()
            
            # Start the timer on the card before answering
            # This is required because answerCard expects timing information
            # that is normally set when the card is retrieved via getCard()
            card.startTimer()
            
            # Answer the card
            collection.sched.answerCard(card, ease)
            collection.autosave()
            
            self.stopEditing()
            return True
            
        except Exception as e:
            self.stopEditing()
            raise e
    
    def resetCard(self, cardId):
        """
        Reset a card to new status
        
        Args:
            cardId (int): ID of the card to reset
            
        Returns:
            bool: True if successful
        """
        collection = self.collection()
        if collection is None:
            return False
            
        try:
            card = collection.getCard(cardId)
            if card is None:
                raise Exception(f"Card with ID '{cardId}' does not exist")
            
            self.startEditing()
            
            # Reset card to new
            collection.sched.forgetCards([cardId])
            collection.autosave()
            
            self.stopEditing()
            return True
            
        except Exception as e:
            self.stopEditing()
            raise e
    
    def forgetCard(self, cardId):
        """
        Forget a card (reset learning progress)
        
        Args:
            cardId (int): ID of the card to forget
            
        Returns:
            bool: True if successful
        """
        collection = self.collection()
        if collection is None:
            return False
            
        try:
            card = collection.getCard(cardId)
            if card is None:
                raise Exception(f"Card with ID '{cardId}' does not exist")
            
            self.startEditing()
            
            # Forget the card
            collection.sched.forgetCards([cardId])
            collection.autosave()
            
            self.stopEditing()
            return True
            
        except Exception as e:
            self.stopEditing()
            raise e
    
    def getDueCards(self, deckName=None, limit=10):
        """
        Get cards that are due for review
        
        Args:
            deckName (str, optional): Name of the deck to get cards from
            limit (int): Maximum number of cards to return
            
        Returns:
            list: List of due card IDs
        """
        collection = self.collection()
        if collection is None:
            return []
        
        # Build query
        if deckName:
            deck = collection.decks.byName(deckName)
            if deck is None:
                raise Exception(f"Deck '{deckName}' does not exist")
            query = f"deck:'{deckName}' is:due"
        else:
            query = "is:due"
        
        # Get due cards
        cardIds = collection.findCards(query)
        return cardIds[:limit] if limit else cardIds
    
    def getNewCards(self, deckName=None, limit=10):
        """
        Get new cards for learning
        
        Args:
            deckName (str, optional): Name of the deck to get cards from
            limit (int): Maximum number of cards to return
            
        Returns:
            list: List of new card IDs
        """
        collection = self.collection()
        if collection is None:
            return []
        
        # Build query
        if deckName:
            deck = collection.decks.byName(deckName)
            if deck is None:
                raise Exception(f"Deck '{deckName}' does not exist")
            query = f"deck:'{deckName}' is:new"
        else:
            query = "is:new"
        
        # Get new cards
        cardIds = collection.findCards(query)
        return cardIds[:limit] if limit else cardIds
    
    def _getAnswerButtons(self, card):
        """
        Get available answer buttons for a card
        
        Args:
            card: Anki card object
            
        Returns:
            list: List of button ease values
        """
        collection = self.collection()
        if collection is None:
            return []
            
        try:
            # Get button count from scheduler
            buttonCount = collection.sched.answerButtons(card)
            return list(range(1, buttonCount + 1))
        except:
            # Default buttons if scheduler method fails
            return [1, 2, 3, 4]
    
    def getStudyStats(self, deckName=None):
        """
        Get study statistics for a deck or all decks
        
        Args:
            deckName (str, optional): Name of the deck
            
        Returns:
            dict: Study statistics
        """
        collection = self.collection()
        if collection is None:
            return None
            
        if deckName:
            deck = collection.decks.byName(deckName)
            if deck is None:
                raise Exception(f"Deck '{deckName}' does not exist")
            deckId = deck['id']
            deckFilter = f"did = {deckId}"
        else:
            deckFilter = "1=1"  # All decks
        
        # Get counts from database
        newCount = collection.db.scalar(f"select count() from cards where {deckFilter} and queue = 0") or 0
        learningCount = collection.db.scalar(f"select count() from cards where {deckFilter} and queue in (1, 3)") or 0
        reviewCount = collection.db.scalar(f"select count() from cards where {deckFilter} and queue = 2") or 0
        totalCount = collection.db.scalar(f"select count() from cards where {deckFilter}") or 0
        
        # Get cards studied today
        from datetime import datetime, timedelta
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        todayTimestamp = int(today.timestamp() * 1000)
        
        studiedToday = collection.db.scalar(
            f"select count() from revlog where id > ? and cid in (select id from cards where {deckFilter})", 
            todayTimestamp
        ) or 0
        
        return {
            'deckName': deckName or 'All Decks',
            'newCount': newCount,
            'learningCount': learningCount,
            'reviewCount': reviewCount,
            'totalCards': totalCount,
            'studiedToday': studiedToday
        }
