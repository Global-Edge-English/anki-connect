# Profile Management Module for AnkiConnect
# Copyright (C) 2023 - Profile management functionality
#
# This module provides profile management capabilities for AnkiConnect,
# including creating, switching, and listing Anki profiles.

import aqt
import sqlite3
import os


def verifyString(string):
    """Verify that the input is a string (helper function)"""
    t = type(string)
    return t == str or (hasattr(__builtins__, 'unicode') and t == unicode)


class ProfileManager:
    """Manages Anki profile operations"""
    
    def __init__(self, anki_bridge):
        self.bridge = anki_bridge
    
    def getCurrentProfile(self):
        """Get current profile information"""
        try:
            pm = self.bridge.window().pm
            if pm and hasattr(pm, 'name'):
                return {
                    'name': pm.name,
                    'path': pm.profileFolder() if hasattr(pm, 'profileFolder') else None,
                    'isDefault': pm.name == 'User 1'
                }
            return None
        except Exception as e:
            return {'error': str(e)}

    def getProfiles(self):
        """Get list of available profiles"""
        try:
            pm = self.bridge.window().pm
            if pm and hasattr(pm, 'profiles'):
                profiles = pm.profiles()
                return [{'name': profile} for profile in profiles]
            return []
        except Exception as e:
            return {'error': str(e)}

    def switchProfile(self, profileName):
        """Switch to a different profile"""
        try:
            pm = self.bridge.window().pm
            if not pm:
                return {'error': 'Profile manager not available'}
            
            # Check if profile exists
            if hasattr(pm, 'profiles'):
                available_profiles = pm.profiles()
                if profileName not in available_profiles:
                    return {'error': f'Profile "{profileName}" not found. Available profiles: {available_profiles}'}
            
            # Switch profile
            if hasattr(pm, 'openProfile'):
                pm.openProfile(profileName)
                return {'success': True, 'message': f'Switched to profile: {profileName}'}
            else:
                return {'error': 'Profile switching not supported in this Anki version'}
                
        except Exception as e:
            return {'error': str(e)}

    def createProfile(self, profileName):
        """Create a new profile"""
        try:
            pm = self.bridge.window().pm
            if not pm:
                return {'error': 'Profile manager not available'}
            
            # Check if profile already exists
            if hasattr(pm, 'profiles'):
                existing_profiles = pm.profiles()
                if profileName in existing_profiles:
                    return {'error': f'Profile "{profileName}" already exists. Existing profiles: {existing_profiles}'}
            
            # Validate profile name
            if not verifyString(profileName) or not profileName.strip():
                return {'error': 'Profile name must be a non-empty string'}
            
            # Check for invalid characters that might cause issues
            invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
            if any(char in profileName for char in invalid_chars):
                return {'error': f'Profile name contains invalid characters. Avoid: {invalid_chars}'}
            
            # Create profile
            if hasattr(pm, 'create'):
                pm.create(profileName)
                return {'success': True, 'message': f'Profile "{profileName}" created successfully'}
            elif hasattr(pm, 'createProfile'):
                pm.createProfile(profileName)
                return {'success': True, 'message': f'Profile "{profileName}" created successfully'}
            else:
                return {'error': 'Profile creation not supported in this Anki version'}
                
        except Exception as e:
            return {'error': str(e)}
    
    def deleteProfile(self, profileName):
        """Delete a profile (optional future functionality)"""
        try:
            pm = self.bridge.window().pm
            if not pm:
                return {'error': 'Profile manager not available'}
            
            # Check if profile exists
            if hasattr(pm, 'profiles'):
                existing_profiles = pm.profiles()
                if profileName not in existing_profiles:
                    return {'error': f'Profile "{profileName}" not found. Available profiles: {existing_profiles}'}
            
            # Prevent deletion of default profile
            if profileName == 'User 1':
                return {'error': 'Cannot delete the default "User 1" profile'}
            
            # Delete profile
            if hasattr(pm, 'remove'):
                pm.remove(profileName)
                return {'success': True, 'message': f'Profile "{profileName}" deleted successfully'}
            elif hasattr(pm, 'deleteProfile'):
                pm.deleteProfile(profileName)
                return {'success': True, 'message': f'Profile "{profileName}" deleted successfully'}
            else:
                return {'error': 'Profile deletion not supported in this Anki version'}
                
        except Exception as e:
            return {'error': str(e)}

    def getProfileDbPath(self, profileName):
        """
        Get the database path for a specific profile without switching to it.
        Much faster than switching profiles.
        
        Args:
            profileName (str): Name of the profile
            
        Returns:
            str: Path to the collection.anki2 database file
        """
        try:
            pm = self.bridge.window().pm
            if not pm:
                raise Exception('Profile manager not available')
            
            # Check if profile exists
            if hasattr(pm, 'profiles'):
                available_profiles = pm.profiles()
                if profileName not in available_profiles:
                    raise Exception(f'Profile "{profileName}" not found. Available profiles: {available_profiles}')
            
            # Get base directory for profiles
            if hasattr(pm, 'base'):
                base_dir = pm.base
            else:
                raise Exception('Cannot determine profiles directory')
            
            # Construct path to profile's database
            profile_dir = os.path.join(base_dir, profileName)
            db_path = os.path.join(profile_dir, 'collection.anki2')
            
            if not os.path.exists(db_path):
                raise Exception(f'Database file not found for profile "{profileName}": {db_path}')
            
            return db_path
            
        except Exception as e:
            raise Exception(f'Failed to get database path for profile "{profileName}": {str(e)}')

    def queryProfileDb(self, profileName, query, params=None):
        """
        Execute a database query on a specific profile's database.
        Much faster than switching profiles.
        
        Args:
            profileName (str): Name of the profile (None for current profile)
            query (str): SQL query to execute
            params (tuple): Parameters for the query
            
        Returns:
            Results of the query
        """
        if not profileName:
            # Use current profile's collection
            collection = self.bridge.collection()
            if collection:
                return collection.db.all(query, params or [])
            else:
                raise Exception('No collection available')
        
        # Get database path for the specified profile
        db_path = self.getProfileDbPath(profileName)
        
        # Connect to the database and execute query
        conn = None
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute(query, params or [])
            
            # Fetch results based on query type
            if query.strip().upper().startswith('SELECT'):
                results = cursor.fetchall()
                return results
            else:
                # For non-SELECT queries, return number of affected rows
                return cursor.rowcount
                
        except Exception as e:
            raise Exception(f'Database query failed: {str(e)}')
        finally:
            if conn:
                conn.close()

    def getDeckInfoFromProfile(self, profileName, deckName):
        """
        Get deck information from a specific profile without switching.
        Fast database-level access.
        
        Args:
            profileName (str): Name of the profile (None for current)
            deckName (str): Name of the deck
            
        Returns:
            dict: Deck information
        """
        try:
            # First get deck ID
            deck_query = "SELECT decks FROM col"
            deck_results = self.queryProfileDb(profileName, deck_query)
            
            if not deck_results:
                raise Exception('No deck data found')
            
            import json
            decks_data = json.loads(deck_results[0][0])
            
            # Find the deck by name
            deck_id = None
            for did, deck in decks_data.items():
                if deck['name'] == deckName:
                    deck_id = did
                    break
            
            if not deck_id:
                raise Exception(f'Deck "{deckName}" not found')
            
            # Get card counts
            new_count = self.queryProfileDb(profileName, 
                "SELECT COUNT(*) FROM cards WHERE did = ? AND queue = 0", (deck_id,))[0][0]
            learning_count = self.queryProfileDb(profileName,
                "SELECT COUNT(*) FROM cards WHERE did = ? AND queue IN (1, 3)", (deck_id,))[0][0]
            review_count = self.queryProfileDb(profileName,
                "SELECT COUNT(*) FROM cards WHERE did = ? AND queue = 2", (deck_id,))[0][0]
            total_count = self.queryProfileDb(profileName,
                "SELECT COUNT(*) FROM cards WHERE did = ?", (deck_id,))[0][0]
            
            return {
                'id': int(deck_id),
                'name': deckName,
                'newCount': new_count,
                'learningCount': learning_count,
                'reviewCount': review_count,
                'totalCards': total_count
            }
            
        except Exception as e:
            raise Exception(f'Failed to get deck info from profile "{profileName}": {str(e)}')

    def addNoteToProfile(self, profileName, noteParams):
        """
        Add a note directly to a specific profile's database.
        Fast database-level note creation.
        
        Args:
            profileName (str): Name of the profile
            noteParams: AnkiNoteParams object with note data
            
        Returns:
            int: Note ID if successful
        """
        import time
        import json
        
        try:
            # Get database path for the specified profile
            db_path = self.getProfileDbPath(profileName)
            
            # Ensure we can read/write to the database file
            if not os.access(db_path, os.R_OK | os.W_OK):
                raise Exception(f'No read/write access to database: {db_path}')
            
            # Connect to the database with proper timeout
            conn = sqlite3.connect(db_path, timeout=10.0)
            cursor = conn.cursor()
            
            # Enable WAL mode for better concurrent access
            cursor.execute("PRAGMA journal_mode=WAL")
            
            try:
                # Get collection data
                cursor.execute("SELECT models, decks FROM col")
                row = cursor.fetchone()
                if not row:
                    raise Exception('No collection data found')
                
                models_data = json.loads(row[0])
                decks_data = json.loads(row[1])
                
                # Find the model by name
                model_id = None
                model = None
                for mid, m in models_data.items():
                    if m['name'] == noteParams.modelName:
                        model_id = mid
                        model = m
                        break
                
                if not model_id:
                    raise Exception(f'Model "{noteParams.modelName}" not found')
                
                # Find the deck by name
                deck_id = None
                for did, deck in decks_data.items():
                    if deck['name'] == noteParams.deckName:
                        deck_id = did
                        break
                
                if not deck_id:
                    raise Exception(f'Deck "{noteParams.deckName}" not found')
                
                # Generate timestamps and IDs
                current_time_ms = int(time.time() * 1000)
                note_id = current_time_ms
                
                # Prepare field values in correct order
                field_values = [''] * len(model['flds'])
                for field_name, field_value in noteParams.fields.items():
                    # Find field index
                    for i, field_def in enumerate(model['flds']):
                        if field_def['name'] == field_name:
                            field_values[i] = field_value
                            break
                
                # Create note record
                tags_str = ' '.join(noteParams.tags) if noteParams.tags else ''
                fields_str = '\x1f'.join(field_values)  # Field separator
                
                cursor.execute("""
                    INSERT INTO notes (id, guid, mid, mod, usn, tags, flds, sfld, csum, flags, data)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    note_id,
                    f"note_{note_id}",  # Simple GUID
                    int(model_id),
                    current_time_ms // 1000,  # mod timestamp in seconds
                    -1,  # usn (sync number)
                    tags_str,
                    fields_str,
                    field_values[0] if field_values else '',  # sfld (sort field)
                    0,  # csum (checksum)
                    0,  # flags
                    ''  # data (empty)
                ))
                
                # Create cards for each template
                card_ids = []
                for i, template in enumerate(model['tmpls']):
                    card_id = current_time_ms + i + 1
                    card_ids.append(card_id)
                    
                    cursor.execute("""
                        INSERT INTO cards (id, nid, did, ord, mod, usn, type, queue, due, ivl, factor, reps, lapses, left, odue, odid, flags, data)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        card_id,
                        note_id,
                        int(deck_id),
                        i,  # ord (template order)
                        current_time_ms // 1000,  # mod timestamp in seconds
                        -1,  # usn
                        0,  # type (new card)
                        0,  # queue (new card queue)
                        0,  # due
                        0,  # ivl (interval)
                        2500,  # factor (ease factor)
                        0,  # reps (repetitions)
                        0,  # lapses
                        0,  # left
                        0,  # odue (original due)
                        0,  # odid (original deck id)
                        0,  # flags
                        ''  # data
                    ))
                
                # Commit the transaction
                conn.commit()
                
                # Verify note was actually created
                cursor.execute("SELECT COUNT(*) FROM notes WHERE id = ?", (note_id,))
                note_count = cursor.fetchone()[0]
                if note_count == 0:
                    raise Exception(f'Note was not saved to database - commit may have failed')
                
                # Verify cards were created
                cursor.execute("SELECT COUNT(*) FROM cards WHERE nid = ?", (note_id,))
                card_count = cursor.fetchone()[0]
                if card_count == 0:
                    raise Exception(f'Cards were not created for note {note_id}')
                
                return note_id
                
            finally:
                conn.close()
                
        except Exception as e:
            raise Exception(f'Failed to add note to profile "{profileName}": {str(e)}')

    def createDeckInProfile(self, profileName, deckName):
        """
        Create a deck directly in a specific profile's database.
        Fast database-level deck creation with proper error handling.
        
        Args:
            profileName (str): Name of the profile
            deckName (str): Name of the deck to create
            
        Returns:
            int: Deck ID if successful
        """
        import time
        import json
        
        # Check if target profile is currently loaded - if so, use normal API
        current_profile = self.getCurrentProfile()
        if current_profile and current_profile.get('name') == profileName:
            # Profile is currently loaded - use normal Anki API
            collection = self.bridge.collection()
            if collection:
                deck_id = collection.decks.id(deckName)
                collection.decks.save()  # Ensure changes are saved
                return deck_id
        
        try:
            # Get database path for the specified profile
            db_path = self.getProfileDbPath(profileName)
            
            print(f"DEBUG: Creating deck '{deckName}' in database: {db_path}")
            
            # Connect to the database
            conn = sqlite3.connect(db_path, timeout=30.0)
            cursor = conn.cursor()
            
            # Enable WAL mode for concurrent access
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            
            try:
                # Get current decks data
                cursor.execute("SELECT decks FROM col")
                row = cursor.fetchone()
                if not row:
                    raise Exception('No collection data found')
                
                # Handle empty or null decks data
                decks_json = row[0]
                if not decks_json or decks_json.strip() == '':
                    decks_data = {}
                else:
                    decks_data = json.loads(decks_json)
                
                print(f"DEBUG: Current decks in database: {list(decks_data.keys())}")
                
                # Check if deck already exists
                for did, deck in decks_data.items():
                    if deck['name'] == deckName:
                        print(f"DEBUG: Deck '{deckName}' already exists with ID {did}")
                        return int(did)
                
                # Generate new deck ID
                current_time_ms = int(time.time() * 1000)
                deck_id = str(current_time_ms)
                
                print(f"DEBUG: Creating new deck with ID {deck_id}")
                
                # Create new deck structure
                new_deck = {
                    'id': int(deck_id),
                    'name': deckName,
                    'mod': current_time_ms // 1000,
                    'usn': -1,
                    'desc': '',
                    'dyn': 0,  # Not a filtered deck
                    'conf': 1,  # Default config ID
                    'extendNew': 0,
                    'extendRev': 0,
                    'collapsed': False
                }
                
                # Add new deck to decks data
                decks_data[deck_id] = new_deck
                
                print(f"DEBUG: Updated decks data: {list(decks_data.keys())}")
                
                # Update the collection
                updated_decks_json = json.dumps(decks_data)
                cursor.execute("UPDATE col SET decks = ?, mod = ?", 
                             (updated_decks_json, current_time_ms // 1000))
                
                # Verify the update
                if cursor.rowcount == 0:
                    raise Exception('Failed to update collection decks data - no rows affected')
                
                # Force commit
                conn.commit()
                
                print(f"DEBUG: Database committed successfully")
                
                # Verify the deck was saved
                cursor.execute("SELECT decks FROM col")
                verify_row = cursor.fetchone()
                if verify_row:
                    verify_decks = json.loads(verify_row[0])
                    if deck_id not in verify_decks:
                        raise Exception(f'Deck {deck_id} was not saved to database')
                    print(f"DEBUG: Verified deck exists in database")
                
                return int(deck_id)
                
            finally:
                conn.close()
                
        except Exception as e:
            print(f"DEBUG: Error creating deck: {str(e)}")
            raise Exception(f'Failed to create deck in profile "{profileName}": {str(e)}')

    def createModelInProfile(self, profileName, modelName, fields, templates, css=""):
        """
        Create a model directly in a specific profile's database.
        Fast database-level model creation.
        
        Args:
            profileName (str): Name of the profile
            modelName (str): Name of the model to create
            fields (list): List of field names
            templates (list): List of template dictionaries
            css (str): CSS styling
            
        Returns:
            int: Model ID if successful
        """
        import time
        import json
        
        try:
            # Get database path for the specified profile  
            db_path = self.getProfileDbPath(profileName)
            
            # Connect to the database
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            try:
                # Get current models data
                cursor.execute("SELECT models FROM col")
                row = cursor.fetchone()
                if not row:
                    raise Exception('No collection data found')
                
                # Handle empty or null models data
                models_json = row[0]
                if not models_json or models_json.strip() == '':
                    models_data = {}
                else:
                    models_data = json.loads(models_json)
                
                # Check if model already exists
                for mid, model in models_data.items():
                    if model['name'] == modelName:
                        raise Exception(f'Model "{modelName}" already exists')
                
                # Generate new model ID
                current_time_ms = int(time.time() * 1000)
                model_id = str(current_time_ms)
                
                # Create field definitions
                field_defs = []
                for i, field_name in enumerate(fields):
                    field_defs.append({
                        'name': field_name,
                        'ord': i,
                        'sticky': False,
                        'rtl': False,
                        'font': 'Arial',
                        'size': 20,
                        'description': '',
                        'plainText': False,
                        'collapsed': False,
                        'excludeFromSearch': False
                    })
                
                # Create template definitions
                template_defs = []
                for i, template in enumerate(templates):
                    template_defs.append({
                        'name': template['name'],
                        'ord': i,
                        'qfmt': template['qfmt'],
                        'afmt': template['afmt'],
                        'bqfmt': '',
                        'bafmt': '',
                        'did': None,
                        'bfont': '',
                        'bsize': 0
                    })
                
                # Create new model structure
                new_model = {
                    'id': int(model_id),
                    'name': modelName,
                    'type': 0,  # Standard model
                    'mod': current_time_ms // 1000,
                    'usn': -1,
                    'sortf': 0,  # Sort field index
                    'did': None,  # Deck ID (None = current)
                    'tmpls': template_defs,
                    'flds': field_defs,
                    'css': css,
                    'latexPre': '\\documentclass[12pt]{article}\n\\special{papersize=3in,5in}\n\\usepackage[utf8]{inputenc}\n\\usepackage{amssymb,amsmath}\n\\pagestyle{empty}\n\\setlength{\\parindent}{0in}\n\\begin{document}\n',
                    'latexPost': '\\end{document}',
                    'latexsvg': False,
                    'req': []  # Requirements (calculated later if needed)
                }
                
                # Add new model to models data
                models_data[model_id] = new_model
                
                # Update the collection with proper error checking
                updated_models_json = json.dumps(models_data)
                cursor.execute("UPDATE col SET models = ?, mod = ?", 
                             (updated_models_json, current_time_ms // 1000))
                
                # Verify the update worked
                if cursor.rowcount == 0:
                    raise Exception('Failed to update collection models data')
                
                # Commit the transaction
                conn.commit()
                
                # Verify the model was actually saved
                cursor.execute("SELECT models FROM col")
                verify_row = cursor.fetchone()
                if verify_row:
                    verify_models = json.loads(verify_row[0])
                    if model_id not in verify_models:
                        raise Exception('Model was not properly saved to database')
                
                return int(model_id)
                
            finally:
                conn.close()
                
        except Exception as e:
            raise Exception(f'Failed to create model in profile "{profileName}": {str(e)}')
