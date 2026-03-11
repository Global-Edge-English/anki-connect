# Copyright (C) 2025
# Study and Review Management for AnkiConnect
#
# This module handles card studying, reviewing, and scheduling
# functionality for AnkiConnect.

import anki
import anki.utils
from ..utils.deck_helpers import get_direct_child_decks, get_deck_limits, update_parent_deck_silent

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

        # Determine deck IDs for this deck + subdecks (used for lastAnsweredCardId query)
        if deckName:
            deck_ids = [deck['id']]
            for did, deck_obj in collection.decks.decks.items():
                if deck_obj['name'].startswith(deckName + '::'):
                    deck_ids.append(int(did))
        else:
            deck_ids = None  # all decks

        # Find the most recently answered card for this deck scope
        if deck_ids is not None:
            deck_ids_str = ','.join(str(did) for did in deck_ids)
            last_answered = collection.db.scalar(
                f"SELECT cid FROM revlog "
                f"WHERE cid IN (SELECT id FROM cards WHERE did IN ({deck_ids_str})) "
                f"ORDER BY id DESC LIMIT 1"
            )
        else:
            last_answered = collection.db.scalar(
                "SELECT cid FROM revlog ORDER BY id DESC LIMIT 1"
            )

        # Get card information
        model = card.model()
        note = card.note()
        template = card.template()
        
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
            'templateName': template['name'],
            'deckName': self.bridge.deckNameFromId(card.did),
            'css': model['css'],
            'factor': card.factor,
            'interval': card.ivl,
            'due': card.due,
            'queue': card.queue,
            'type': card.type,
            'noteId': card.nid,
            'buttons': self._getAnswerButtons(card),
            'flagged': card.flags > 0,
            'lastAnsweredCardId': last_answered
        }
    
    def answerCard(self, cardId, ease, timeTakenSeconds=None):
        """
        Answer a card with the specified ease.

        For the v3 scheduler, Anki's Rust backend enforces a "top of queue"
        contract: only the card at position 0 of get_queued_cards() (for the
        currently selected deck) can be answered via answer_card_raw.

        Race condition: in a multi-user setup, a learning-step card may become
        due BETWEEN the client's getNextReviewCard call and this answerCard
        call (e.g. user spends several minutes on a card). When that happens,
        the learning card jumps to position 0, blocking the target card.

        Fix: re-select the card's own deck, then loop through the queue. Any
        card that is NOT the target is temporarily suspended (removed from
        queue) so the target rises to position 0. Once answered, all
        temporarily suspended cards are immediately unsuspended in a finally
        block — their scheduling state (due timestamp, interval, factor) is
        fully preserved.

        Side effects of the suspend/unsuspend cycle:
          - The blocking card's mod/usn is bumped (causes a harmless sync).
          - Daily study counts and card scheduling data are NOT affected.
          - Single-threaded execution means no other user observes the
            suspended state.

        Args:
            cardId (int): ID of the card to answer
            ease (int): Ease/difficulty rating (1=Again, 2=Hard, 3=Good, 4=Easy)
            timeTakenSeconds (float, optional): Time taken to answer in seconds.
                                               If not provided, defaults to 0.

        Returns:
            bool: True if successful
        """
        collection = self.collection()
        if collection is None:
            return False

        # Validate card exists and capture its deck ID before editing begins
        try:
            db_card = collection.getCard(cardId)
        except Exception:
            raise Exception(f"Card with ID '{cardId}' does not exist")

        # Validate ease
        if ease < 1 or ease > 4:
            raise Exception(f"Invalid ease value '{ease}'. Must be between 1-4")

        # Re-select the card's own deck so get_queued_cards() returns cards
        # from the correct deck context (fixes the multi-user deck-switching
        # problem where another user's getNextReviewCard may have changed the
        # globally selected deck).
        collection.decks.select(db_card.did)

        self.startEditing()

        # Cards temporarily suspended to let the target card reach position 0.
        # Always unsuspended in the finally block regardless of outcome.
        temporarily_suspended = []

        try:
            # Use a single batch-peek to find the target card in the queue,
            # then batch-suspend everything ahead of it in one DB call.
            # This is O(1) DB operations regardless of how many cards are
            # ahead, and handles any deck size efficiently.
            #
            # fetch_limit=10000 returns all queued cards for the current
            # session; after the due-value fix in undoAnswerCard the target
            # will always be within the first handful of results.
            queued_cards = collection.sched.get_queued_cards(fetch_limit=10000)

            to_suspend = []
            found = False
            for qc in queued_cards.cards:
                if qc.card.id == cardId:
                    found = True
                    break
                to_suspend.append(qc.card.id)

            if not found:
                raise Exception(
                    f"Card {cardId} is not in the review queue for its deck. "
                    f"It may be suspended, buried, or not yet due."
                )

            # Batch-suspend everything ahead of the target card (one DB call).
            if to_suspend:
                collection.sched.suspendCards(to_suspend)
                temporarily_suspended = to_suspend

            card = collection.sched.getCard()

            if card is None or card.id != cardId:
                raise Exception(
                    f"Card {cardId} could not be reached at queue position 0 "
                    f"after suspending {len(temporarily_suspended)} blocking card(s). "
                    f"This is unexpected — please check the deck configuration."
                )

            # Answer the card (card already has its timer started by getCard())
            collection.sched.answerCard(card, ease)

            # If custom time was provided, update the revlog entry directly.
            # The entry was just created by answerCard().
            if timeTakenSeconds is not None:
                time_ms = int(timeTakenSeconds * 1000)
                collection.db.execute(
                    "UPDATE revlog SET time = ? WHERE id = ("
                    "SELECT id FROM revlog WHERE cid = ? ORDER BY id DESC LIMIT 1"
                    ")",
                    time_ms, cardId
                )

            collection.autosave()

        finally:
            # Always restore temporarily suspended blocking cards.
            # Their scheduling state (due timestamp, interval, factor, type)
            # is fully preserved by the Anki backend on unsuspend.
            if temporarily_suspended:
                try:
                    collection.sched.unsuspendCards(temporarily_suspended)
                except Exception:
                    # Log but don't mask the original error (if any).
                    pass

            self.stopEditing()

        return True
    
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
        Get available answer buttons for a card with timing information
        
        Args:
            card: Anki card object
            
        Returns:
            list: List of button dictionaries with ease, label, and timing
        """
        collection = self.collection()
        if collection is None:
            return []
            
        try:
            # Get button count from scheduler
            buttonCount = collection.sched.answerButtons(card)
            
            # Button labels mapping
            button_labels = {
                1: "Again",
                2: "Hard" if buttonCount >= 4 else "Good",
                3: "Good" if buttonCount >= 4 else "Easy",
                4: "Easy"
            }
            
            # Try to get timing information (v3 scheduler)
            timings = []
            try:
                # Get scheduling states for the card from backend
                states = collection._backend.get_scheduling_states(card.id)
                # Get timing labels for each button from backend
                timing_labels = collection._backend.describe_next_states(states)
                timings = list(timing_labels)
            except (AttributeError, Exception):
                # Fallback for older versions or if method not available
                timings = [""] * buttonCount
            
            # Build button info with ease, label, and timing
            buttons = []
            for i in range(1, buttonCount + 1):
                buttons.append({
                    'ease': i,
                    'label': button_labels.get(i, f"Button {i}"),
                    'timing': timings[i - 1] if i <= len(timings) else ""
                })
            
            return buttons
            
        except Exception as e:
            # Default buttons if scheduler method fails
            return [
                {'ease': 1, 'label': 'Again', 'timing': ''},
                {'ease': 2, 'label': 'Hard', 'timing': ''},
                {'ease': 3, 'label': 'Good', 'timing': ''},
                {'ease': 4, 'label': 'Easy', 'timing': ''}
            ]
    
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
    
    def getDeckTimeStats(self, deckName=None, period="allTime"):
        """
        Get time statistics for a deck showing average seconds per card
        
        Args:
            deckName (str, optional): Name of the deck (None for all decks)
            period (str): Time period - "today", "last7days", "last30days", "allTime"
            
        Returns:
            dict: Time statistics including average time per card
        """
        collection = self.collection()
        if collection is None:
            return None
        
        from datetime import datetime, timedelta
        
        # Calculate timestamp based on period
        if period == "today":
            cutoff = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            cutoffTimestamp = int(cutoff.timestamp() * 1000)
            periodDesc = "today"
        elif period == "last7days":
            cutoff = datetime.now() - timedelta(days=7)
            cutoffTimestamp = int(cutoff.timestamp() * 1000)
            periodDesc = "last 7 days"
        elif period == "last30days":
            cutoff = datetime.now() - timedelta(days=30)
            cutoffTimestamp = int(cutoff.timestamp() * 1000)
            periodDesc = "last 30 days"
        else:  # allTime
            cutoffTimestamp = 0
            periodDesc = "all time"
        
        # Build deck filter
        if deckName:
            deck = collection.decks.byName(deckName)
            if deck is None:
                raise Exception(f"Deck '{deckName}' does not exist")
            
            # Get all deck IDs for this deck and its children
            # This includes the parent deck and all nested child decks
            deckIds = [deck['id']]
            for deckId, deckObj in collection.decks.decks.items():
                # Check if this deck is a child of the specified deck
                if deckObj['name'].startswith(deckName + '::'):
                    deckIds.append(int(deckId))
            
            # Create filter for all these decks
            deckIdsStr = ','.join(str(did) for did in deckIds)
            deckFilter = f"and cid in (select id from cards where did in ({deckIdsStr}))"
        else:
            deckFilter = ""
        
        # Query review log for time statistics
        # time column in revlog is in milliseconds
        query = f"""
            select 
                count(*) as review_count,
                sum(time) as total_time_ms,
                avg(time) as avg_time_ms
            from revlog 
            where id > ? {deckFilter}
        """
        
        result = collection.db.first(query, cutoffTimestamp)
        
        if result is None or result[0] == 0:
            return {
                'deckName': deckName or 'All Decks',
                'period': periodDesc,
                'totalReviews': 0,
                'totalTimeSeconds': 0.0,
                'averageTimePerCardSeconds': 0.0
            }
        
        review_count, total_time_ms, avg_time_ms = result
        
        # Convert milliseconds to seconds
        total_time_seconds = (total_time_ms / 1000.0) if total_time_ms else 0.0
        avg_time_seconds = (avg_time_ms / 1000.0) if avg_time_ms else 0.0
        
        return {
            'deckName': deckName or 'All Decks',
            'period': periodDesc,
            'totalReviews': review_count,
            'totalTimeSeconds': round(total_time_seconds, 2),
            'averageTimePerCardSeconds': round(avg_time_seconds, 2)
        }
    
    def setDeckStudyOptions(self, deckName, newCardsPerDay=None, reviewsPerDay=None):
        """
        Set study options for a specific deck only (new cards per day and/or reviews per day)
        This will create a deck-specific config if the deck is currently using a shared config.
        
        If the deck is a child deck (contains '::'), this will also automatically update the
        parent deck's limits to be the sum of all its children's limits.
        
        NOTE: This method does not work with filtered (dynamic) decks, as they use a different
        configuration system stored directly in the deck object.
        
        Args:
            deckName (str): Name of the deck to configure
            newCardsPerDay (int, optional): Maximum new cards to study per day
            reviewsPerDay (int, optional): Maximum review cards per day
            
        Returns:
            dict: Updated configuration with the new settings
        """
        collection = self.collection()
        if collection is None:
            raise Exception("Collection not available")
        
        # Get the deck
        deck = collection.decks.byName(deckName)
        if deck is None:
            raise Exception(f"Deck '{deckName}' does not exist")
        
        # Check if this is a filtered/dynamic deck
        # Filtered decks have 'dyn' field set to 1 and don't use standard configs
        if deck.get('dyn', 0):
            raise Exception(f"Cannot set study options for filtered deck '{deckName}'. "
                          "Filtered decks use a different configuration system stored in the deck object itself. "
                          "They do not use the standard deck configuration system.")
        
        deck_id = deck['id']
        current_config_id = deck.get('conf', 1)
        
        self.startEditing()
        
        try:
            # Check if this config is shared by other decks
            decks_using_config = []
            for did, d in collection.decks.decks.items():
                if d.get('conf') == current_config_id and did != str(deck_id):
                    decks_using_config.append(d['name'])
            
            # If config is shared, clone it for this deck only
            if len(decks_using_config) > 0:
                # Clone the current config
                current_config = collection.decks.getConf(current_config_id)
                new_config_name = f"{deckName} Options"
                new_config_id = collection.decks.confId(new_config_name, current_config)
                
                # Assign the new config to this deck
                deck['conf'] = new_config_id
                collection.decks.save(deck)
                
                # Get the newly created config
                config = collection.decks.getConf(new_config_id)
            else:
                # Config is not shared, safe to modify directly
                config = collection.decks.confForDid(deck_id)
            
            if config is None:
                raise Exception(f"Could not get configuration for deck '{deckName}'")
            
            # Update new cards per day if specified
            if newCardsPerDay is not None:
                if newCardsPerDay < 0:
                    raise Exception("newCardsPerDay must be >= 0")
                config['new']['perDay'] = newCardsPerDay
            
            # Update reviews per day if specified
            if reviewsPerDay is not None:
                if reviewsPerDay < 0:
                    raise Exception("reviewsPerDay must be >= 0")
                config['rev']['perDay'] = reviewsPerDay
            
            # Save the configuration
            config['mod'] = anki.utils.intTime()
            config['usn'] = collection.usn()
            collection.decks.save(config)
            collection.autosave()
            
            self.stopEditing()
            
            # Store result before parent update
            result = {
                'deckName': deckName,
                'configId': config['id'],
                'configName': config['name'],
                'newCardsPerDay': config['new']['perDay'],
                'reviewsPerDay': config['rev']['perDay'],
                'wasShared': len(decks_using_config) > 0,
                'createdNewConfig': len(decks_using_config) > 0
            }
            
            # If this is a child deck, update parent deck's limits to be sum of all children
            if '::' in deckName:
                # Extract parent deck name
                parent_name = deckName.rsplit('::', 1)[0]
                
                # Get all direct children of the parent
                child_decks = get_direct_child_decks(collection, parent_name)
                
                # Calculate sum of all children's limits
                total_new_cards = 0
                total_reviews = 0
                
                for child_deck in child_decks:
                    new_cards, reviews = get_deck_limits(collection, child_deck)
                    total_new_cards += new_cards
                    total_reviews += reviews
                
                # Silently update parent deck with the calculated sums
                update_parent_deck_silent(collection, parent_name, total_new_cards, total_reviews)
            
            return result
            
        except Exception as e:
            self.stopEditing()
            raise e
    
    def extendNewCardLimit(self, deckName, additionalCards):
        """
        Extend today's new card limit for a specific deck using Anki's backend custom study API.
        Uses the same mechanism as Anki's native "Increase today's new card limit" option.
        This properly extends TODAY's limit without permanently modifying deck configuration.
        
        Args:
            deckName (str): Name of the deck
            additionalCards (int): Number of additional new cards to allow today
            
        Returns:
            dict: Information about the extended limit
        """
        collection = self.collection()
        if collection is None:
            raise Exception("Collection not available")
        
        # Get the deck
        deck = collection.decks.byName(deckName)
        if deck is None:
            raise Exception(f"Deck '{deckName}' does not exist")
        
        if additionalCards <= 0:
            raise Exception("additionalCards must be > 0")
        
        deck_id = deck['id']
        
        self.startEditing()
        
        try:
            # Use Anki's backend custom_study API (same as the UI uses)
            from anki.scheduler import CustomStudyRequest
            
            request = CustomStudyRequest()
            request.deck_id = deck_id
            request.new_limit_delta = additionalCards
            
            # This extends the limit using Anki's Rust backend
            collection.sched.custom_study(request)
            
            # Get updated deck to read the extendNew value
            deck = collection.decks.get(deck_id)
            extend_new = deck.get('extendNew', additionalCards)
            
            collection.autosave()
            self.stopEditing()
            
            return {
                'deckName': deckName,
                'additionalCardsAllowed': additionalCards,
                'totalExtended': extend_new,
                'message': f"Extended new card limit by {additionalCards} cards for today"
            }
            
        except Exception as e:
            self.stopEditing()
            raise e
    
    def enableStudyForgotten(self, deckName, days=1, filteredDeckName=None):
        """
        Enable studying cards that were forgotten (answered "Again") in the last X days.
        Creates a filtered deck for reviewing forgotten cards.
        Uses Anki's backend custom_study API to match native behavior exactly.
        
        Args:
            deckName (str): Name of the source deck
            days (int): Look back this many days for forgotten cards (default: 1 = today only)
            filteredDeckName (str, optional): Custom name for the filtered deck. If not provided, uses Anki's default.
            
        Returns:
            dict: Information about the created filtered deck
        """
        collection = self.collection()
        if collection is None:
            raise Exception("Collection not available")
        
        # Verify source deck exists
        source_deck = collection.decks.byName(deckName)
        if source_deck is None:
            raise Exception(f"Deck '{deckName}' does not exist")
        
        if days <= 0:
            raise Exception("days must be > 0")
        
        deck_id = source_deck['id']
        
        self.startEditing()
        
        try:
            # Use Anki's backend custom_study API (same as the UI uses)
            from anki.scheduler import CustomStudyRequest
            
            request = CustomStudyRequest()
            request.deck_id = deck_id
            request.forgot_days = days
            
            # This creates the filtered deck using Anki's Rust backend
            collection.sched.custom_study(request)
            
            # Get the created filtered deck (Anki names it "Custom Study Session")
            filtered_deck_name = "Custom Study Session"
            filtered_deck = collection.decks.byName(filtered_deck_name)
            
            if filtered_deck is None:
                raise Exception("Failed to create custom study deck")
            
            # If custom name requested, rename it
            if filteredDeckName and filteredDeckName != filtered_deck_name:
                filtered_deck['name'] = filteredDeckName
                collection.decks.save(filtered_deck)
                collection.decks.rename(filtered_deck, filteredDeckName)
                filtered_deck_name = filteredDeckName
            
            # Count cards in the filtered deck
            card_count = collection.db.scalar(
                "select count() from cards where did = ?", filtered_deck['id']
            ) or 0
            
            collection.autosave()
            self.stopEditing()
            
            return {
                'sourceDeck': deckName,
                'filteredDeckName': filtered_deck_name,
                'filteredDeckId': filtered_deck['id'],
                'days': days,
                'cardsFound': card_count,
                'message': f"Created filtered deck with {card_count} forgotten cards from last {days} day(s)"
            }
            
        except Exception as e:
            self.stopEditing()
            raise e
    
    def createCustomStudy(self, deckName, newCardsPerDay=None, reviewsPerDay=None, 
                         studyForgottenToday=False, extendNewLimit=None):
        """
        Combined API for creating a custom study session with various options.
        
        Args:
            deckName (str): Name of the deck to configure
            newCardsPerDay (int, optional): Set new cards per day limit
            reviewsPerDay (int, optional): Set reviews per day limit
            studyForgottenToday (bool): Create filtered deck for forgotten cards today
            extendNewLimit (int, optional): Extend today's new card limit by this many cards
            
        Returns:
            dict: Results of all requested operations
        """
        results = {
            'deckName': deckName,
            'operations': {}
        }
        
        # Set deck study options if requested
        if newCardsPerDay is not None or reviewsPerDay is not None:
            try:
                config_result = self.setDeckStudyOptions(
                    deckName, newCardsPerDay, reviewsPerDay
                )
                results['operations']['studyOptions'] = {
                    'success': True,
                    'data': config_result
                }
            except Exception as e:
                results['operations']['studyOptions'] = {
                    'success': False,
                    'error': str(e)
                }
        
        # Extend new card limit if requested
        if extendNewLimit is not None:
            try:
                extend_result = self.extendNewCardLimit(deckName, extendNewLimit)
                results['operations']['extendNewLimit'] = {
                    'success': True,
                    'data': extend_result
                }
            except Exception as e:
                results['operations']['extendNewLimit'] = {
                    'success': False,
                    'error': str(e)
                }
        
        # Create forgotten cards filtered deck if requested
        if studyForgottenToday:
            try:
                forgotten_result = self.enableStudyForgotten(deckName, days=1)
                results['operations']['studyForgotten'] = {
                    'success': True,
                    'data': forgotten_result
                }
            except Exception as e:
                results['operations']['studyForgotten'] = {
                    'success': False,
                    'error': str(e)
                }
        
        return results
    
    def undoAnswerCard(self, cardId, deckName):
        """
        Undo the most recent answer for a specific card by card ID.

        This works by:
        1. Optionally validating the card belongs to deckName (or a subdeck)
        2. Finding the most recent revlog entry for the card
        3. Reading the pre-answer state from that entry (lastIvl, prior factor)
        4. Deleting the revlog entry
        5. Restoring the card's scheduling state to what it was before the answer

        After undo, the card will be immediately available in the review queue.

        Args:
            cardId (int): ID of the card whose most recent answer should be undone
            deckName (str, optional): Parent deck name. If provided, the card must
                                      belong to this deck or one of its subdecks,
                                      otherwise the undo is rejected.

        Returns:
            dict: {
                'cardId': int,
                'restoredState': str,   # 'new', 'learning', or 'review'
                'restoredInterval': int  # interval before the answer
            }

        Raises:
            Exception: If card doesn't exist, card not in deck, or no answer history
        """
        collection = self.collection()
        if collection is None:
            raise Exception("Collection not available")

        if cardId is None:
            raise Exception("cardId is required")

        # Verify card exists
        try:
            card = collection.getCard(cardId)
        except Exception:
            raise Exception(f"Card with ID '{cardId}' does not exist")

        # If deckName provided, validate the card belongs to that deck or a subdeck
        if deckName:
            # Verify the parent deck exists
            parent_deck = collection.decks.byName(deckName)
            if parent_deck is None:
                raise Exception(f"Deck '{deckName}' does not exist")

            card_deck_name = collection.decks.get(card.did)['name']
            if card_deck_name != deckName and not card_deck_name.startswith(deckName + '::'):
                raise Exception(
                    f"Card '{cardId}' does not belong to deck '{deckName}' or its subdecks "
                    f"(card is in '{card_deck_name}')"
                )

        # Find the most recent revlog entry for this card
        revlog_entry = collection.db.first(
            "SELECT id, ease, ivl, lastIvl, factor, time, type "
            "FROM revlog WHERE cid = ? ORDER BY id DESC LIMIT 1",
            cardId
        )

        if revlog_entry is None:
            raise Exception(f"No answer history found for card '{cardId}'")

        revlog_id, ease, ivl, last_ivl, factor, time_taken, review_type = revlog_entry

        # Get the prior factor from the second-most-recent revlog entry (if any)
        prior_entry = collection.db.first(
            "SELECT factor FROM revlog WHERE cid = ? ORDER BY id DESC LIMIT 1 OFFSET 1",
            cardId
        )
        prior_factor = prior_entry[0] if prior_entry and prior_entry[0] else 2500

        # Delete the most recent revlog entry to erase this answer from history
        collection.db.execute("DELETE FROM revlog WHERE id = ?", revlog_id)

        # Restore card state based on the interval before the answer (last_ivl):
        #   last_ivl == 0  → card was new before this answer
        #   last_ivl < 0   → card was in a learning step (value = negative seconds for next step)
        #   last_ivl > 0   → card was a mature review card (value = days)

        self.startEditing()
        try:
            import time as time_module

            # ----------------------------------------------------------------
            # Decrement the deck's "shown today" counter for the card type
            # that was active BEFORE the answer. This is the same per-deck
            # counter that Anki's native undo adjusts (stored as
            # deck['newToday'] / deck['lrnToday'] / deck['revToday'], each a
            # [day_number, count] tuple). Without this, the daily budget stays
            # short by 1 even after the revlog entry is removed.
            # ----------------------------------------------------------------
            today = collection.sched.today
            deck = collection.decks.get(card.did)
            if deck:
                if last_ivl == 0:
                    today_field = 'newToday'
                elif last_ivl < 0:
                    today_field = 'lrnToday'
                else:
                    today_field = 'revToday'

                today_entry = deck.get(today_field)
                if today_entry and today_entry[0] == today and today_entry[1] > 0:
                    deck[today_field][1] -= 1
                    collection.decks.save(deck)

            # ----------------------------------------------------------------
            # Restore the card's scheduling state
            # ----------------------------------------------------------------
            if last_ivl == 0:
                # Card was NEW before this answer.
                # forgetCards() resets to queue=0 via Anki's proper pipeline.
                collection.sched.forgetCards([cardId])

                # forgetCards() assigns due = card.ord (its position number),
                # which buries it deep in the new queue. Re-fetch and set due=0
                # to put it at the FRONT of the new queue so it shows up next.
                card = collection.getCard(cardId)
                card.due = 0
                card.flush()
                restored_state = 'new'

            elif last_ivl < 0:
                # Card was in a LEARNING step — restore to learning queue.
                # Setting due=0 (Unix epoch, year 1970) makes this the most
                # overdue learning card possible, guaranteeing it will be
                # returned first by get_queued_cards() ahead of all other
                # learning, new, and review cards.
                card.type = 1
                card.queue = 1
                card.ivl = 0
                card.due = 0
                card.factor = prior_factor
                card.flush()
                restored_state = 'learning'

            else:
                # Card was a mature REVIEW card — restore to review queue.
                # Setting due=today-999999 (≈2700 years ago) makes this the
                # most overdue review card possible, placing it ahead of all
                # other review cards in the queue. Only intraday learning cards
                # (typically 0–3) can appear before it, so answerCard's
                # batch-peek approach suspends at most a handful of blockers.
                card.type = 2
                card.queue = 2
                card.ivl = last_ivl
                card.due = today - 999999
                card.factor = prior_factor
                card.flush()
                restored_state = 'review'

            # Force the scheduler to recount new/learn/review from the
            # database. Without this the in-memory counts stay stale.
            collection.sched.reset()

            collection.autosave()
            self.stopEditing()

            return {
                'cardId': cardId,
                'restoredState': restored_state,
                'restoredInterval': last_ivl
            }

        except Exception as e:
            self.stopEditing()
            raise e

    def getDeckReviewsByDay(self, deckName, days=14):
        """
        Get the number of reviews completed per day for the last N days.
        Uses the same approach as Anki's built-in statistics calendar.
        
        Args:
            deckName (str): Name of the deck (required)
            days (int): Number of days to look back (default: 14)
            
        Returns:
            dict: Daily review statistics with breakdown by card type
        """
        collection = self.collection()
        if collection is None:
            raise Exception("Collection not available")
        
        # Get the deck
        deck = collection.decks.byName(deckName)
        if deck is None:
            raise Exception(f"Deck '{deckName}' does not exist")
        
        deck_id = deck['id']
        
        # Get all deck IDs (parent + children)
        deck_ids = [deck_id]
        for did, deck_obj in collection.decks.decks.items():
            if deck_obj['name'].startswith(deckName + '::'):
                deck_ids.append(int(did))
        
        deck_ids_str = ','.join(str(did) for did in deck_ids)
        
        # Get day cutoff from scheduler (this is when "today" ENDS, typically 4am tomorrow)
        day_cutoff = collection.sched.day_cutoff
        
        # Calculate start of "today" in Anki's system (24 hours before day_cutoff)
        day_start = day_cutoff - 86400
        
        # Calculate timestamp for N days ago
        cutoff_timestamp = (day_cutoff - (days * 86400)) * 1000
        
        # Query revlog using Anki's approach
        # This matches the _done() method in stats.py
        query = f"""
            SELECT 
                cast((id/1000.0 - ?) / 86400.0 as int) as day,
                sum(case when type = 0 then 1 else 0 end) as learning,
                sum(case when type = 1 then 1 else 0 end) as review,
                sum(case when type = 2 then 1 else 0 end) as relearn,
                sum(case when type = 3 then 1 else 0 end) as filtered,
                count(*) as total
            FROM revlog
            WHERE id > ?
                AND cid IN (SELECT id FROM cards WHERE did IN ({deck_ids_str}))
            GROUP BY day
            ORDER BY day
        """
        
        results = collection.db.all(query, day_cutoff, cutoff_timestamp)
        
        # Process results into a more readable format
        from datetime import datetime, timedelta
        
        stats = []
        total_reviews = 0
        
        for row in results:
            day_offset, learning, review, relearn, filtered, total = row
            
            # Calculate actual date using day_start (not day_cutoff) to get correct calendar dates
            date_timestamp = day_start + (day_offset * 86400)
            date = datetime.fromtimestamp(date_timestamp).strftime('%Y-%m-%d')
            
            stats.append({
                'date': date,
                'dayNumber': day_offset,
                'learning': learning,
                'review': review,
                'relearn': relearn,
                'filtered': filtered,
                'total': total
            })
            
            total_reviews += total
        
        # Calculate average
        avg_per_day = round(total_reviews / days, 1) if days > 0 else 0.0
        
        # Get current count of new cards available in the deck
        new_cards_available = collection.db.scalar(
            f"SELECT COUNT(*) FROM cards WHERE did IN ({deck_ids_str}) AND queue = 0"
        ) or 0
        
        return {
            'deckName': deckName,
            'days': days,
            'stats': stats,
            'totalReviews': total_reviews,
            'averagePerDay': avg_per_day,
            'newCardsAvailable': new_cards_available
        }
