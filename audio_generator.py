"""
Audio generator for AnkiConnect
Handles ElevenLabs TTS API integration
"""

import random
import hashlib
import time
import sys

if sys.version_info[0] < 3:
    import urllib2
    from urllib2 import Request, urlopen, HTTPError
else:
    from urllib.request import Request, urlopen
    from urllib.error import HTTPError

try:
    from .config_manager import ConfigManager
except ImportError:
    from config_manager import ConfigManager

# Global voice cache - shared across all instances
_GLOBAL_VOICES_CACHE = None


class AudioGenerator:
    """Generates audio using ElevenLabs TTS API"""
    
    def __init__(self):
        self.config_manager = ConfigManager()
        self.api_base_url = "https://api.elevenlabs.io/v1"
    
    def get_available_voices(self):
        """
        Fetch available voices from ElevenLabs API (uses global cache)
        
        Returns:
            list: List of voice dictionaries with 'voice_id', 'name', and 'labels' (gender)
        """
        global _GLOBAL_VOICES_CACHE
        
        # Return cached voices if available
        if _GLOBAL_VOICES_CACHE is not None:
            return _GLOBAL_VOICES_CACHE
        
        api_key = self.config_manager.get_api_key()
        if not api_key:
            raise Exception("ElevenLabs API key not set")
        
        url = f"{self.api_base_url}/voices"
        
        try:
            import json
            request = Request(url)
            request.add_header('xi-api-key', api_key)
            
            response = urlopen(request, timeout=10)
            data = json.loads(response.read().decode('utf-8'))
            
            # Cache the voices globally
            _GLOBAL_VOICES_CACHE = data.get('voices', [])
            return _GLOBAL_VOICES_CACHE
            
        except Exception as e:
            # If fetching voices fails, return empty list
            # The generate_audio method will use a fallback default voice
            return []
    
    def select_voice(self):
        """
        Select a random voice from available voices
        
        Returns:
            str: Voice ID
        """
        voices = self.get_available_voices()
        
        # If no voices available, use ElevenLabs default voice
        if not voices:
            return "21m00Tcm4TlvDq8ikWAM"  # Default fallback voice
        
        # Randomly select a voice
        selected_voice = random.choice(voices)
        return selected_voice['voice_id']
    
    def generate_audio(self, text, language="en"):
        """
        Generate audio from text using ElevenLabs API
        
        Args:
            text: Text to convert to speech
            language: Language code (e.g., "en", "es", "fr")
        
        Returns:
            tuple: (audio_bytes, filename) or raises Exception
        """
        api_key = self.config_manager.get_api_key()
        
        if not api_key:
            raise Exception("ElevenLabs API key not set. Go to Tools → AnkiConnect Settings")
        
        # Select voice randomly
        voice_id = self.select_voice()
        
        # Generate unique filename
        timestamp = int(time.time())
        text_hash = hashlib.md5(text.encode('utf-8')).hexdigest()[:8]
        filename = f"audio_{timestamp}_{text_hash}.mp3"
        
        # Prepare API request
        url = f"{self.api_base_url}/text-to-speech/{voice_id}"
        
        # Request body
        import json
        body = json.dumps({
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75
            }
        })
        
        # Make request
        try:
            request = Request(url, data=body.encode('utf-8'))
            request.add_header('xi-api-key', api_key)
            request.add_header('Content-Type', 'application/json')
            
            response = urlopen(request, timeout=30)
            audio_data = response.read()
            
            if not audio_data:
                raise Exception("Empty response from ElevenLabs API")
            
            return audio_data, filename
            
        except HTTPError as e:
            error_body = e.read().decode('utf-8') if e.fp else str(e)
            raise Exception(f"ElevenLabs API error ({e.code}): {error_body}")
        except Exception as e:
            raise Exception(f"Failed to generate audio: {str(e)}")
    
    def test_api_key(self):
        """
        Test if the API key is valid
        
        Returns:
            bool: True if valid, False otherwise
        """
        try:
            # Try to generate a short audio as a test
            self.generate_audio("Test", "en", "male")
            return True
        except:
            return False
