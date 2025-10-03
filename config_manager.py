"""
Configuration manager for AnkiConnect
Handles reading and writing of plugin configuration
Stores config outside addon folder to persist across updates
"""

import json
import os

class ConfigManager:
    def __init__(self):
        # Store config in Anki's base folder (outside addons folder)
        # This way it persists across addon updates
        try:
            import aqt
            # Get Anki's base directory (parent of addons folder)
            base_dir = os.path.dirname(aqt.mw.addonManager.addonsFolder())
            self.config_path = os.path.join(base_dir, 'ankiconnect_config.json')
        except:
            # Fallback to home directory if Anki not available
            self.config_path = os.path.expanduser('~/.ankiconnect_config.json')
        
        # Ensure config file exists with defaults
        self._ensure_config_exists()
    
    def _ensure_config_exists(self):
        """Create config file with defaults if it doesn't exist"""
        if not os.path.exists(self.config_path):
            default_config = {
                "elevenlabs_api_key": ""
            }
            self.save_config(default_config)
    
    def load_config(self):
        """Load configuration from file"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading config from {self.config_path}: {e}")
            return {"elevenlabs_api_key": ""}
    
    def save_config(self, config):
        """Save configuration to file"""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
            print(f"Config saved to {self.config_path}")
            return True
        except Exception as e:
            print(f"Error saving config to {self.config_path}: {e}")
            return False
    
    def get_api_key(self):
        """Get ElevenLabs API key"""
        config = self.load_config()
        api_key = config.get("elevenlabs_api_key", "")
        print(f"Retrieved API key (length: {len(api_key) if api_key else 0})")
        return api_key
    
    def set_api_key(self, api_key):
        """Set ElevenLabs API key"""
        config = self.load_config()
        config["elevenlabs_api_key"] = api_key
        result = self.save_config(config)
        if result:
            print(f"API key set successfully (length: {len(api_key) if api_key else 0})")
        return result
