# Copyright (C) 2025
# Note and Model Management for AnkiConnect
#
# This module handles note type (model) creation, modification, deletion,
# and deck management functionality for AnkiConnect.

import anki
import anki.utils

class NoteManager:
    """Manages note types (models) and decks in Anki"""
    
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

    # Model (Note Type) Management
    
    def createModel(self, modelName, fields, templates, css=""):
        """
        Create a new note type (model) in Anki
        
        Args:
            modelName (str): Name of the new model
            fields (list): List of field names
            templates (list): List of template dictionaries with 'name', 'qfmt', 'afmt'
            css (str): CSS styling for the model
            
        Returns:
            int: Model ID if successful
            
        Raises:
            Exception: If model already exists or creation fails
        """
        collection = self.collection()
        if collection is None:
            return None
        
        # Check if model already exists
        if collection.models.byName(modelName):
            raise Exception(f"Model '{modelName}' already exists")
        
        self.startEditing()
        
        try:
            # Create new model
            model = collection.models.new(modelName)
            
            # Add fields
            for fieldName in fields:
                field = collection.models.newField(fieldName)
                collection.models.addField(model, field)
            
            # Add templates
            for templateData in templates:
                template = collection.models.newTemplate(templateData['name'])
                template['qfmt'] = templateData['qfmt']  # Question format
                template['afmt'] = templateData['afmt']  # Answer format
                collection.models.addTemplate(model, template)
            
            # Set CSS if provided
            if css:
                model['css'] = css
            
            # Save the model
            collection.models.add(model)
            collection.models.save(model)
            
            self.stopEditing()
            return model['id']
            
        except Exception as e:
            self.stopEditing()
            raise e

    def updateModel(self, modelId, modelName=None, fields=None, templates=None, css=None):
        """
        Update an existing note type (model)
        
        Args:
            modelId (int): ID of the model to update
            modelName (str, optional): New name for the model
            fields (list, optional): New list of field names
            templates (list, optional): New list of templates
            css (str, optional): New CSS styling
            
        Returns:
            bool: True if successful
            
        Raises:
            Exception: If model doesn't exist or update fails
        """
        collection = self.collection()
        if collection is None:
            return False
        
        model = collection.models.get(modelId)
        if model is None:
            raise Exception(f"Model with ID '{modelId}' does not exist")
        
        self.startEditing()
        
        try:
            # Update model name if provided
            if modelName is not None:
                # Check if new name already exists (and it's not the same model)
                existing = collection.models.byName(modelName)
                if existing and existing['id'] != modelId:
                    raise Exception(f"Model '{modelName}' already exists")
                model['name'] = modelName
            
            # Update fields if provided
            if fields is not None:
                # Remove existing fields
                for field in model['flds'][:]:
                    collection.models.remField(model, field)
                
                # Add new fields
                for fieldName in fields:
                    field = collection.models.newField(fieldName)
                    collection.models.addField(model, field)
            
            # Update templates if provided
            if templates is not None:
                # Remove existing templates
                for template in model['tmpls'][:]:
                    collection.models.remTemplate(model, template)
                
                # Add new templates
                for templateData in templates:
                    template = collection.models.newTemplate(templateData['name'])
                    template['qfmt'] = templateData['qfmt']
                    template['afmt'] = templateData['afmt']
                    collection.models.addTemplate(model, template)
            
            # Update CSS if provided
            if css is not None:
                model['css'] = css
            
            # Save the model
            collection.models.save(model)
            
            self.stopEditing()
            return True
            
        except Exception as e:
            self.stopEditing()
            raise e

    def deleteModel(self, modelId):
        """
        Delete a note type (model)
        
        Args:
            modelId (int): ID of the model to delete
            
        Returns:
            bool: True if successful
            
        Raises:
            Exception: If model doesn't exist or is in use
        """
        collection = self.collection()
        if collection is None:
            return False
        
        model = collection.models.get(modelId)
        if model is None:
            raise Exception(f"Model with ID '{modelId}' does not exist")
        
        # Check if model is in use
        noteCount = collection.models.useCount(model)
        if noteCount > 0:
            raise Exception(f"Cannot delete model '{model['name']}': {noteCount} notes are using this model")
        
        self.startEditing()
        collection.models.rem(model)
        self.stopEditing()
        
        return True

    # Deck Management
    
    def createDeck(self, deckName):
        """
        Create a new deck
        
        Args:
            deckName (str): Name of the new deck
            
        Returns:
            int: Deck ID if successful
            
        Raises:
            Exception: If deck already exists
        """
        collection = self.collection()
        if collection is None:
            return None
        
        # Check if deck already exists
        if collection.decks.byName(deckName):
            raise Exception(f"Deck '{deckName}' already exists")
        
        self.startEditing()
        deckId = collection.decks.id(deckName)
        self.stopEditing()
        
        return deckId

    def deleteDeck(self, deckName, deleteCards=False):
        """
        Delete a deck
        
        Args:
            deckName (str): Name of the deck to delete
            deleteCards (bool): Whether to delete cards or move them to default deck
            
        Returns:
            bool: True if successful
        """
        collection = self.collection()
        if collection is None:
            return False
            
        deck = collection.decks.byName(deckName)
        if deck is None:
            raise Exception(f"Deck '{deckName}' does not exist")
        
        self.startEditing()
        
        try:
            # Use Anki's backend remove_decks method
            from anki.decks import DeckId
            collection.decks.remove([DeckId(deck['id'])])
            
            self.stopEditing()
            return True
        except Exception as e:
            self.stopEditing()
            raise e

    def renameDeck(self, oldName, newName):
        """
        Rename a deck
        
        Args:
            oldName (str): Current deck name
            newName (str): New deck name
            
        Returns:
            bool: True if successful
        """
        collection = self.collection()
        if collection is None:
            return False
            
        deck = collection.decks.byName(oldName)
        if deck is None:
            raise Exception(f"Deck '{oldName}' does not exist")
            
        # Check if new name already exists
        if collection.decks.byName(newName):
            raise Exception(f"Deck '{newName}' already exists")
        
        self.startEditing()
        deck['name'] = newName
        collection.decks.save(deck)
        self.stopEditing()
        
        return True

    # Utility Methods
    
    def getModelInfo(self, modelId):
        """
        Get detailed information about a model
        
        Args:
            modelId (int): ID of the model
            
        Returns:
            dict: Model information including fields, templates, css
        """
        collection = self.collection()
        if collection is None:
            return None
            
        model = collection.models.get(modelId)
        if model is None:
            return None
            
        return {
            'id': model['id'],
            'name': model['name'],
            'fields': [field['name'] for field in model['flds']],
            'templates': [
                {
                    'name': template['name'],
                    'qfmt': template['qfmt'],
                    'afmt': template['afmt']
                }
                for template in model['tmpls']
            ],
            'css': model['css'],
            'noteCount': collection.models.useCount(model)
        }

    def getDeckInfo(self, deckName, includeTimeStats=True, period="allTime", wantSingleDeckStats=False):
        """
        Get detailed information about a deck and its child decks
        
        Args:
            deckName (str): Name of the deck
            includeTimeStats (bool): Whether to include time statistics (default: True)
            period (str): Time period for stats - "today", "last7days", "last30days", "allTime"
            wantSingleDeckStats (bool): If True, returns only the single deck's stats (no child decks) (default: False)
            
        Returns:
            list: Array of deck information. If wantSingleDeckStats is True, returns only [parent_deck_info].
                  Otherwise, if deck has children, returns [child1_info, child2_info, ...].
                  If deck has no children, returns [deck_info]. Each element contains stats and time stats if requested.
        """
        collection = self.collection()
        if collection is None:
            return None
            
        deck = collection.decks.byName(deckName)
        if deck is None:
            return None
        
        # Get the deck tree with counts that respect daily limits
        tree = collection.sched.deck_due_tree()
        
        # Helper function to get deck info
        def getDeckStatsInfo(deckObj, deckId):
            # Find the specific deck node in the tree
            deckNode = collection.decks.find_deck_in_tree(tree, deckId)
            
            if deckNode is None:
                return None
            
            # Use the scheduler's counts which respect daily limits
            deckInfo = {
                'id': deckId,
                'name': deckObj['name'],
                'newCount': deckNode.new_count,  # Respects daily new card limit
                'learningCount': deckNode.learn_count,
                'reviewCount': deckNode.review_count,  # Respects daily review limit
                'totalCards': deckNode.total_including_children,  # Total cards in deck and children
                'isFiltered': bool(deckObj.get('dyn', 0))  # True if this is a filtered/dynamic deck
            }
            
            # Add time statistics if requested
            if includeTimeStats:
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
                
                # Query review log for time statistics for this specific deck
                query = """
                    select 
                        count(*) as review_count,
                        sum(time) as total_time_ms,
                        avg(time) as avg_time_ms
                    from revlog 
                    where id > ? and cid in (select id from cards where did = ?)
                """
                
                timeResult = collection.db.first(query, cutoffTimestamp, deckId)
                
                if timeResult and timeResult[0] > 0:
                    review_count, total_time_ms, avg_time_ms = timeResult
                    total_time_seconds = (total_time_ms / 1000.0) if total_time_ms else 0.0
                    avg_time_seconds = (avg_time_ms / 1000.0) if avg_time_ms else 0.0
                    
                    deckInfo['timeStats'] = {
                        'period': periodDesc,
                        'totalReviews': review_count,
                        'totalTimeSeconds': round(total_time_seconds, 2),
                        'averageTimePerCardSeconds': round(avg_time_seconds, 2)
                    }
                else:
                    deckInfo['timeStats'] = {
                        'period': periodDesc,
                        'totalReviews': 0,
                        'totalTimeSeconds': 0.0,
                        'averageTimePerCardSeconds': 0.0
                    }
            
            return deckInfo
        
        # If wantSingleDeckStats is True, return only the single deck (no children)
        if wantSingleDeckStats:
            parentInfo = getDeckStatsInfo(deck, deck['id'])
            if parentInfo is None:
                return None
            return [parentInfo]
        
        # Find all child decks
        childDecks = []
        for deckId, deckObj in collection.decks.decks.items():
            # Check if this deck is a direct or nested child of the specified deck
            if deckObj['name'].startswith(deckName + '::'):
                childDecks.append((deckObj['name'], int(deckId), deckObj))
        
        # Sort child decks by name for consistent ordering
        childDecks.sort(key=lambda x: x[0])
        
        result = []
        
        # If there are child decks, return only the children (not the parent)
        if childDecks:
            for childName, childId, childDeck in childDecks:
                childInfo = getDeckStatsInfo(childDeck, childId)
                if childInfo is not None:
                    # Strip the parent deck prefix from the name
                    childInfo['name'] = childName.replace(deckName + '::', '', 1)
                    result.append(childInfo)
        else:
            # No children, return just the parent deck
            parentInfo = getDeckStatsInfo(deck, deck['id'])
            if parentInfo is None:
                return None
            result.append(parentInfo)
        
        return result
