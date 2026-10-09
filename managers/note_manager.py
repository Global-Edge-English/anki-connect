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

    def refreshGuiIfEnabled(self):
        """Menu-gated modern GUI refresh (delegates to the bridge)."""
        self.bridge.refreshGuiIfEnabled()

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
        if collection.models.by_name(modelName):
            raise Exception(f"Model '{modelName}' already exists")
        
        # No startEditing()/stopEditing() wrapper: requireReset() prints a stack
        # trace + forces a full UI reset on every call. models.add/save persist
        # directly; refresh the GUI only when the menu toggle is on.
        # Create new model
        model = collection.models.new(modelName)

        # Add fields
        for fieldName in fields:
            field = collection.models.new_field(fieldName)
            collection.models.addField(model, field)

        # Add templates
        for templateData in templates:
            template = collection.models.new_template(templateData['name'])
            template['qfmt'] = templateData['qfmt']  # Question format
            template['afmt'] = templateData['afmt']  # Answer format
            collection.models.addTemplate(model, template)

        # Set CSS if provided
        if css:
            model['css'] = css

        # Save the model
        collection.models.add(model)
        collection.models.save(model)

        self.refreshGuiIfEnabled()
        return model['id']

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
        
        # No startEditing()/stopEditing() wrapper: requireReset() prints a stack
        # trace + forces a full UI reset on every call. models.save() persists
        # directly; GUI refresh is gated on the menu toggle (see the return path).
        try:
            # Update model name if provided
            if modelName is not None:
                # Check if new name already exists (and it's not the same model)
                existing = collection.models.by_name(modelName)
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
                    field = collection.models.new_field(fieldName)
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
                    template = collection.models.new_template(templateData['name'])
                    template['qfmt'] = templateData['qfmt']
                    template['afmt'] = templateData['afmt']
                    collection.models.addTemplate(model, template)
            
            # Update CSS if provided
            if css is not None:
                model['css'] = css
            
            # Save the model
            collection.models.save(model)

            self.refreshGuiIfEnabled()
            return True

        except Exception:
            raise

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
        if collection.decks.by_name(deckName):
            raise Exception(f"Deck '{deckName}' already exists")
        
        deckId = collection.decks.id(deckName)
        self.refreshGuiIfEnabled()

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
            
        deck = collection.decks.by_name(deckName)
        if deck is None:
            raise Exception(f"Deck '{deckName}' does not exist")
        
        # No startEditing()/stopEditing(): requireReset() printed a stack trace
        # + full UI reset per call. remove() persists directly; refresh the GUI
        # only when the menu toggle is on.
        from anki.decks import DeckId
        collection.decks.remove([DeckId(deck['id'])])
        self.refreshGuiIfEnabled()
        return True

    def resetDecks(self, ownerDeck, deckNames, keepDeckNames=None):
        """
        Reset some or all of one student's decks.

        Deletes every note with a card in the target decks (or their subdecks).
        Target decks listed in keepDeckNames survive empty, keeping their deck
        ids and deck options; their non-kept subdecks are removed. Other target
        decks are removed together with their subdecks. Every filtered (custom
        study) deck under ownerDeck is removed first, whatever the targets.

        A kept deck below a removed deck is removed with it, so keep the whole
        path down to it (e.g. the root as well as 'root::Text').

        Safe to retry: a second call finds nothing left to delete or remove.

        Args:
            ownerDeck (str): The student's top-level deck (no '::')
            deckNames (list): Decks to reset: ownerDeck itself and/or its subdecks
            keepDeckNames (list, optional): Decks to empty but not remove

        Returns:
            dict: {
                'notesDeleted': int,
                'deletedNoteIds': [int],
                'decksRemoved': [str],  # includes subdecks and filtered decks
                'missing': [str]  # entries of deckNames that don't exist
            }

        Raises:
            Exception: If an argument is malformed or a deck name is outside ownerDeck
        """
        collection = self.collection()
        if collection is None:
            raise Exception("Collection not available")

        if not isinstance(ownerDeck, str) or not ownerDeck.strip() or '::' in ownerDeck:
            raise Exception("ownerDeck must be a top-level deck name")
        if not isinstance(deckNames, list) or not deckNames:
            raise Exception("deckNames must be a non-empty list")
        if keepDeckNames is None:
            keepDeckNames = []
        if not isinstance(keepDeckNames, list):
            raise Exception("keepDeckNames must be a list")

        # Anki deck names are case-insensitive, so every name comparison below
        # is done on .lower().
        owner_lower = ownerDeck.lower()
        owner_prefix = owner_lower + '::'
        for name in deckNames + keepDeckNames:
            if not isinstance(name, str):
                raise Exception("Deck names must be strings")
            name_lower = name.lower()
            if name_lower != owner_lower and not name_lower.startswith(owner_prefix):
                raise Exception(f"Deck '{name}' does not belong to deck '{ownerDeck}'")

        # A missing owner means there is nothing to reset. Don't raise
        # "does not exist": the API treats that as a broken deck and repairs.
        owner = collection.decks.by_name(ownerDeck)
        if owner is None:
            return {
                'notesDeleted': 0,
                'deletedNoteIds': [],
                'decksRemoved': [],
                'missing': list(deckNames),
            }
        owner_id = int(owner['id'])

        # Anki runs with the cyclic GC disabled (see CLAUDE.md), so this method
        # only keeps plain ints and strings: each deck dict is read and dropped
        # straight away, and no nested function walks the tree.
        from anki.decks import DeckId

        # Remove filtered decks first. A card in a filtered deck has `did` set
        # to the filtered deck and its home deck in `odid`; removing the
        # filtered deck sends the card home. Doing it up front puts every card
        # back in its home deck before the notes are picked by `did`, cards
        # from decks that aren't being reset simply go home, and no filtered
        # deck is left to return cards into a home deck removed below.
        decks_removed = []
        removed_lower = set()
        dyn_ids = []
        for name, did in collection.decks.children(owner_id):
            deck = collection.decks.get(did, default=False)
            if deck is not None and deck.get('dyn'):
                dyn_ids.append(int(did))
                decks_removed.append(name)
                removed_lower.add(name.lower())
        if dyn_ids:
            collection.decks.remove([DeckId(did) for did in dyn_ids])

        # Resolve the targets to plain (id, name) pairs. A target that was a
        # filtered deck is already gone, so it isn't reported as missing.
        targets = []
        target_ids = set()
        missing = []
        for name in deckNames:
            if name.lower() in removed_lower:
                continue
            deck = collection.decks.by_name(name)
            if deck is None:
                missing.append(name)
                continue
            did = int(deck['id'])
            if did not in target_ids:
                target_ids.add(did)
                targets.append((did, str(deck['name'])))

        all_dids = set()
        for did, _name in targets:
            for child_id in collection.decks.deck_and_child_ids(did):
                all_dids.add(int(child_id))

        # `odid` also catches cards of these decks that sit in a filtered deck
        # outside ownerDeck (e.g. a top-level "Custom Study Session"). Keep the
        # `odid != 0`: it lets SQLite use the partial idx_cards_odid index
        # instead of scanning every card in the shared collection.
        nids = []
        if all_dids:
            ids = ','.join(str(did) for did in all_dids)  # ints only
            nids = collection.db.list(
                f"SELECT DISTINCT nid FROM cards "
                f"WHERE did IN ({ids}) OR (odid != 0 AND odid IN ({ids}))"
            )
        if nids:
            collection.remove_notes(nids)

        # Pick the decks to remove. A kept target stays; only its top-most
        # non-kept subdecks go (deeper ones go with them). A target that isn't
        # kept goes with its whole subtree.
        keep_lower = {name.lower() for name in keepDeckNames}
        candidates = []
        for did, name in targets:
            if name.lower() not in keep_lower:
                candidates.append((name, did))
                continue
            for child_name, child_id in collection.decks.children(did):
                child_lower = child_name.lower()
                if child_lower in keep_lower:
                    continue
                if child_name.rsplit('::', 1)[0].lower() in keep_lower:
                    candidates.append((child_name, int(child_id)))

        # Shallowest first, so a deck whose ancestor is already being removed
        # is skipped (targets 'X::Foo' and 'X::Foo::Bar' remove only 'X::Foo').
        candidates.sort(key=lambda candidate: candidate[0].count('::'))
        remove_ids = []
        root_lower = set()
        for name, did in candidates:
            name_lower = name.lower()
            if name_lower in root_lower:
                continue
            parts = name_lower.split('::')
            ancestor_removed = False
            for depth in range(1, len(parts)):
                if '::'.join(parts[:depth]) in root_lower:
                    ancestor_removed = True
                    break
            if ancestor_removed:
                continue
            root_lower.add(name_lower)
            remove_ids.append(did)
            # Names must be read now: they are gone after remove().
            subtree_names = [name] + [child_name for child_name, _id in collection.decks.children(did)]
            for subtree_name in subtree_names:
                if subtree_name.lower() not in removed_lower:
                    removed_lower.add(subtree_name.lower())
                    decks_removed.append(subtree_name)

        if remove_ids:
            collection.decks.remove([DeckId(did) for did in remove_ids])

        self.refreshGuiIfEnabled()

        return {
            'notesDeleted': len(nids),
            'deletedNoteIds': [int(nid) for nid in nids],
            'decksRemoved': decks_removed,
            'missing': missing,
        }

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
            deck = collection.decks.by_name(deckName)
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
        parent_deck = collection.decks.by_name(deckName)
        if parent_deck is None:
            raise Exception(f"Deck '{deckName}' does not exist")

        # Verify note exists
        try:
            note = collection.get_note(noteId)
        except Exception:
            try:
                note = collection.get_note(noteId)
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

        # Modern Anki: remove_notes() runs in its own Rust transaction and fires
        # the op-framework UI hooks itself - no startEditing/stopEditing wrapper
        # (that calls the obsolete aqt.mw.requireReset() full UI reset) and no
        # autosave() (deprecated no-op). Mirrors addNote/addAudioNote.
        try:
            from anki.notes import NoteId
            collection.remove_notes([NoteId(noteId)])
        except (ImportError, AttributeError, TypeError):
            # Older Anki: legacy remNotes needs the UI-reset wrapper.
            self.startEditing()
            try:
                collection.remove_notes([noteId])
            finally:
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

        deck = collection.decks.by_name(deckName)
        if deck is None:
            return None

        # Build a deck-id → due-counts index ONCE with an ITERATIVE walk that
        # stores only plain ints — never the protobuf nodes. The previous code
        # used a recursive nested closure (`def _index` that calls itself),
        # which forms a reference cycle that retains the entire deck tree. Anki
        # disables the cyclic GC at startup (aqt/main.py: gc.disable()), so that
        # cycle was never collected and leaked the whole tree on every call.
        # getDeckInfo is polled heavily (getCard + getOwnDeckStats), so it grew
        # the process until OOM. Iterating + storing ints breaks the cycle and
        # retains nothing from the backend tree past this function. See INCIDENT.md.
        tree = collection.sched.deck_due_tree()
        tree_counts = {}
        stack = [tree]
        while stack:
            node = stack.pop()
            tree_counts[int(node.deck_id)] = (
                node.new_count,
                node.learn_count,
                node.review_count,
                node.total_including_children,
            )
            stack.extend(node.children)

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
            counts = tree_counts.get(deck_id)
            if counts is None:
                continue
            new_count, learn_count, review_count, total_including_children = counts

            info = {
                'id': deck_id,
                'name': deck_obj['name'],
                'newCount': new_count,
                'learningCount': learn_count,
                'reviewCount': review_count,
                'totalCards': total_including_children,
                'isFiltered': bool(deck_obj.get('dyn', 0)),
            }

            try:
                config = collection.decks.config_dict_for_deck_id(deck_id)
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
