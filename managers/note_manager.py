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
                # Get current field names
                existing_field_names = [f['name'] for f in model['flds']]
                new_field_names = fields
                
                # Find fields to remove (in old but not in new)
                fields_to_remove = [f for f in model['flds'] if f['name'] not in new_field_names]
                
                # Find fields to add (in new but not in old)
                fields_to_add = [name for name in new_field_names if name not in existing_field_names]
                
                # Remove fields that are no longer needed (in reverse order to avoid index issues)
                for field in reversed(fields_to_remove):
                    collection.models.remField(model, field)
                
                # Add new fields
                for fieldName in fields_to_add:
                    field = collection.models.newField(fieldName)
                    collection.models.addField(model, field)
                
                # Reorder fields to match the desired order
                # Create a mapping of field names to field objects
                field_map = {f['name']: f for f in model['flds']}
                
                # Reorder the fields list to match new_field_names order
                reordered_fields = []
                for idx, fieldName in enumerate(new_field_names):
                    if fieldName in field_map:
                        field = field_map[fieldName]
                        field['ord'] = idx  # Update the ordinal
                        reordered_fields.append(field)
                
                # Replace the fields list with the reordered one
                model['flds'] = reordered_fields
            
            # Update templates if provided
            if templates is not None:
                # Get current template names
                existing_template_names = [t['name'] for t in model['tmpls']]
                new_template_names = [t['name'] for t in templates]
                
                # Find templates to remove (in old but not in new)
                templates_to_remove = [t for t in model['tmpls'] if t['name'] not in new_template_names]
                
                # Find templates to add (in new but not in old)
                new_template_data = {t['name']: t for t in templates}
                templates_to_add = [t for t in templates if t['name'] not in existing_template_names]
                
                # Update existing templates (modify qfmt/afmt for templates that exist in both)
                for template in model['tmpls']:
                    if template['name'] in new_template_data:
                        template['qfmt'] = new_template_data[template['name']]['qfmt']
                        template['afmt'] = new_template_data[template['name']]['afmt']
                
                # Remove templates that are no longer needed (in reverse order)
                # Only remove if we'll still have at least 1 template after
                if len(model['tmpls']) - len(templates_to_remove) + len(templates_to_add) >= 1:
                    for template in reversed(templates_to_remove):
                        collection.models.remTemplate(model, template)
                elif len(templates_to_remove) > 0:
                    raise Exception("Cannot remove all templates - model must have at least 1 template")
                
                # Add new templates
                for templateData in templates_to_add:
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

    # Note Retrieval & Deletion

    def getNoteIds(self, deckName=None, page=1, pageSize=50, query=None):
        """
        Get a paginated list of note IDs using an optional deck name and/or search query.

        Supports the same search syntax as Anki's card browser (e.g. "flag:1", "is:due",
        "tag:mytag", "front:hello", "added:7", etc.).

        Args:
            deckName (str, optional): Name of the parent deck (subdecks are automatically
                                      included). If omitted, searches across all decks.
            page (int): 1-indexed page number (default: 1)
            pageSize (int): Number of note IDs per page (default: 50)
            query (str, optional): Additional Anki search query string. Combined with
                                   deckName filter using AND if both are provided.

        Returns:
            dict: { noteIds, page, pageSize, total, totalPages, query }

        Examples:
            # All notes in a deck (including subdecks)
            getNoteIds(deckName="MyDeck")

            # Notes in a deck matching a search filter
            getNoteIds(deckName="MyDeck", query="is:due")

            # Search across all decks with a query (no deckName)
            getNoteIds(query="tag:important flag:1")

            # Free-form search just like the card browser
            getNoteIds(query="front:hello added:7")
        """
        collection = self.collection()
        if collection is None:
            raise Exception("Collection not available")

        if page < 1:
            raise Exception("page must be >= 1")
        if pageSize < 1:
            raise Exception("pageSize must be >= 1")

        # Build the final search query
        parts = []

        if deckName:
            # Verify deck exists
            deck = collection.decks.byName(deckName)
            if deck is None:
                raise Exception(f"Deck '{deckName}' does not exist")
            # deck:"name" automatically includes all subdecks in Anki
            parts.append(f"deck:\"{deckName}\"")

        if query and query.strip():
            parts.append(query.strip())

        if not parts:
            raise Exception("At least one of 'deckName' or 'query' must be provided")

        final_query = " ".join(parts)

        try:
            all_note_ids = list(collection.find_notes(final_query))
        except Exception as e:
            raise Exception(f"Invalid search query '{final_query}': {str(e)}")

        total = len(all_note_ids)
        total_pages = max(1, (total + pageSize - 1) // pageSize)

        start = (page - 1) * pageSize
        end = start + pageSize
        page_note_ids = all_note_ids[start:end]

        return {
            'noteIds': page_note_ids,
            'page': page,
            'pageSize': pageSize,
            'total': total,
            'totalPages': total_pages,
            'query': final_query
        }

    def deleteNote(self, noteId, deckName):
        """
        Delete a note (and all its cards) by note ID.

        Args:
            noteId (int): ID of the note to delete
            deckName (str): Parent deck name. At least one card of the note must
                            belong to this deck or one of its subdecks — the
                            request is rejected otherwise.

        Returns:
            bool: True if successful

        Raises:
            Exception: If the note does not exist, is not in the deck, or deletion fails
        """
        collection = self.collection()
        if collection is None:
            raise Exception("Collection not available")

        if noteId is None:
            raise Exception("noteId is required")

        if not deckName:
            raise Exception("deckName is required")

        # Verify deck exists
        parent_deck = collection.decks.byName(deckName)
        if parent_deck is None:
            raise Exception(f"Deck '{deckName}' does not exist")

        # Verify note exists
        try:
            note = collection.get_note(noteId)
        except Exception:
            try:
                note = collection.getNote(noteId)
            except Exception:
                raise Exception(f"Note with ID '{noteId}' does not exist")

        # Validate at least one card belongs to deckName or a subdeck
        cards = note.cards()
        if not cards:
            raise Exception(f"Note '{noteId}' has no cards")

        has_match = any(
            collection.decks.get(card.did)['name'] == deckName or
            collection.decks.get(card.did)['name'].startswith(deckName + '::')
            for card in cards
        )
        if not has_match:
            card_deck = collection.decks.get(cards[0].did)['name']
            raise Exception(
                f"Note '{noteId}' does not belong to deck '{deckName}' or its subdecks "
                f"(note is in '{card_deck}')"
            )

        self.startEditing()
        try:
            # Use modern remove_notes API (Anki 2.1.x)
            try:
                from anki.notes import NoteId
                collection.remove_notes([NoteId(noteId)])
            except (ImportError, AttributeError, TypeError):
                # Fallback for older Anki versions
                collection.remNotes([noteId])

            collection.autosave()
            self.stopEditing()
            return True
        except Exception as e:
            self.stopEditing()
            raise e

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

        # Build a deck-id → tree-node index ONCE so per-deck lookups are O(1)
        # instead of an O(N) walk via collection.decks.find_deck_in_tree per
        # child (was O(N²) total for a parent with many children).
        tree = collection.sched.deck_due_tree()
        tree_index = {}
        def _index(node):
            tree_index[int(node.deck_id)] = node
            for child in node.children:
                _index(child)
        _index(tree)

        # Resolve the set of decks we'll compute stats for. children() is one
        # backend RPC over a cached deck-name lookup and returns ALL descendants,
        # replacing the O(total_decks) Python loop over collection.decks.decks.
        if wantSingleDeckStats:
            target_decks = [(deck['name'], int(deck['id']), deck)]
        else:
            descendants = list(collection.decks.children(deck['id']))
            if descendants:
                target_decks = []
                for child_name, child_id in descendants:
                    child_deck = collection.decks.get(child_id)
                    if child_deck is not None:
                        target_decks.append((child_name, int(child_id), child_deck))
                target_decks.sort(key=lambda x: x[0])
            else:
                target_decks = [(deck['name'], int(deck['id']), deck)]

        # Compute time stats for ALL target decks in one query. Replaces N
        # separate revlog scans with one INNER JOIN + GROUP BY — biggest win
        # on collections with many child decks and a large revlog.
        time_stats = {}
        period_desc = ""
        if includeTimeStats and target_decks:
            from datetime import datetime, timedelta

            if period == "today":
                cutoff = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                cutoff_ts = int(cutoff.timestamp() * 1000)
                period_desc = "today"
            elif period == "last7days":
                cutoff_ts = int((datetime.now() - timedelta(days=7)).timestamp() * 1000)
                period_desc = "last 7 days"
            elif period == "last30days":
                cutoff_ts = int((datetime.now() - timedelta(days=30)).timestamp() * 1000)
                period_desc = "last 30 days"
            else:
                cutoff_ts = 0
                period_desc = "all time"

            deck_ids = [did for _, did, _ in target_decks]
            placeholders = ','.join('?' * len(deck_ids))
            rows = collection.db.all(
                f"SELECT c.did, COUNT(*), SUM(r.time), AVG(r.time) "
                f"FROM revlog r INNER JOIN cards c ON r.cid = c.id "
                f"WHERE r.id > ? AND c.did IN ({placeholders}) "
                f"GROUP BY c.did",
                cutoff_ts, *deck_ids,
            )
            for did, count, total_ms, avg_ms in rows:
                time_stats[int(did)] = (count, total_ms or 0, avg_ms or 0)

        # Build the result list.
        result = []
        for deck_name_full, deck_id, deck_obj in target_decks:
            node = tree_index.get(deck_id)
            if node is None:
                continue

            info = {
                'id': deck_id,
                'name': deck_obj['name'],
                'newCount': node.new_count,
                'learningCount': node.learn_count,
                'reviewCount': node.review_count,
                'totalCards': node.total_including_children,
                'isFiltered': bool(deck_obj.get('dyn', 0)),
            }

            try:
                config = collection.decks.confForDid(deck_id)
                if config is not None:
                    info['newCardsPerDay'] = config.get('new', {}).get('perDay', 0)
                    info['reviewsPerDay'] = config.get('rev', {}).get('perDay', 0)
                else:
                    info['newCardsPerDay'] = 0
                    info['reviewsPerDay'] = 0
            except Exception:
                info['newCardsPerDay'] = 0
                info['reviewsPerDay'] = 0

            if includeTimeStats:
                stats = time_stats.get(deck_id)
                if stats and stats[0] > 0:
                    count, total_ms, avg_ms = stats
                    info['timeStats'] = {
                        'period': period_desc,
                        'totalReviews': count,
                        'totalTimeSeconds': round(total_ms / 1000.0, 2),
                        'averageTimePerCardSeconds': round(avg_ms / 1000.0, 2),
                    }
                else:
                    info['timeStats'] = {
                        'period': period_desc,
                        'totalReviews': 0,
                        'totalTimeSeconds': 0.0,
                        'averageTimePerCardSeconds': 0.0,
                    }

            # Children get the parent prefix stripped from their name (legacy behavior).
            if not wantSingleDeckStats and deck_name_full != deck['name']:
                info['name'] = deck_name_full.replace(deckName + '::', '', 1)

            result.append(info)

        if not result:
            return None
        return result
