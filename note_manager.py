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
        collection.decks.rem(deck['id'], deleteCards)
        self.stopEditing()
        
        return True

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

    def getDeckInfo(self, deckName):
        """
        Get detailed information about a deck
        
        Args:
            deckName (str): Name of the deck
            
        Returns:
            dict: Deck information
        """
        collection = self.collection()
        if collection is None:
            return None
            
        deck = collection.decks.byName(deckName)
        if deck is None:
            return None
            
        # Get card counts using database queries for compatibility
        deckId = deck['id']
        
        # Get card counts directly from database
        newCount = collection.db.scalar("select count() from cards where did = ? and queue = 0", deckId) or 0
        lrnCount = collection.db.scalar("select count() from cards where did = ? and queue in (1, 3)", deckId) or 0 
        revCount = collection.db.scalar("select count() from cards where did = ? and queue = 2", deckId) or 0
        totalCount = collection.db.scalar("select count() from cards where did = ?", deckId) or 0
        
        return {
            'id': deck['id'],
            'name': deck['name'],
            'newCount': newCount,
            'learningCount': lrnCount,
            'reviewCount': revCount,
            'totalCards': totalCount
        }
