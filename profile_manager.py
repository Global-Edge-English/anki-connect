# Profile Management Module for AnkiConnect
# Copyright (C) 2023 - Profile management functionality
#
# This module provides profile management capabilities for AnkiConnect,
# including creating, switching, and listing Anki profiles.

import aqt


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
