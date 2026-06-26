# Copyright (C) 2025
# Persistent configuration for Global Edge AnkiConnect.
#
# Stores a small JSON file in Anki's BASE folder (the parent of the addons
# folder) rather than inside the add-on directory, so settings survive add-on
# updates/redeploys as well as restarts. Mirrors the approach used by the
# earlier ElevenLabs settings (added in a1f9fc2, removed in b46d389) and
# reintroduced for the "refresh GUI after API writes" toggle.

import json
import os

CONFIG_FILENAME = 'ankiconnect_config.json'


class ConfigManager:
    """Read/write a flat JSON settings file that outlives add-on updates."""

    def __init__(self):
        try:
            import aqt
            # Parent of the addons folder = Anki's base dir, which is NOT wiped
            # when this add-on is updated/reinstalled.
            base_dir = os.path.dirname(aqt.mw.addonManager.addonsFolder())
            self.config_path = os.path.join(base_dir, CONFIG_FILENAME)
        except Exception:
            # Anki not available (tests / odd contexts) — fall back to $HOME.
            self.config_path = os.path.expanduser('~/.' + CONFIG_FILENAME)

    def load(self):
        """Return the config dict, or {} if missing/unreadable."""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}

    def save(self, config):
        """Write the whole config dict. Returns True on success."""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
            return True
        except Exception:
            return False

    def get(self, key, default=None):
        return self.load().get(key, default)

    def set(self, key, value):
        config = self.load()
        config[key] = value
        return self.save(config)
