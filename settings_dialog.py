"""
Settings dialog for AnkiConnect
Provides GUI for configuring ElevenLabs API key
"""

import sys

# Try PyQt6 first (for newer Anki versions), then fall back to PyQt5
try:
    from PyQt6.QtWidgets import (
        QDialog, QVBoxLayout, QHBoxLayout, 
        QLabel, QLineEdit, QPushButton, QMessageBox
    )
    from PyQt6.QtCore import Qt
except ImportError:
    from PyQt5.QtWidgets import (
        QDialog, QVBoxLayout, QHBoxLayout,
        QLabel, QLineEdit, QPushButton, QMessageBox
    )
    from PyQt5.QtCore import Qt

try:
    from .config_manager import ConfigManager
except ImportError:
    from config_manager import ConfigManager


class SettingsDialog(QDialog):
    """Dialog for configuring AnkiConnect settings"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.config_manager = ConfigManager()
        self.setup_ui()
        self.load_settings()
    
    def setup_ui(self):
        """Setup the user interface"""
        self.setWindowTitle("AnkiConnect Settings")
        self.setMinimumWidth(400)
        
        layout = QVBoxLayout()
        
        # API Key section
        api_key_label = QLabel("ElevenLabs API Key:")
        layout.addWidget(api_key_label)
        
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password if hasattr(QLineEdit, 'EchoMode') else QLineEdit.Password)
        self.api_key_input.setPlaceholderText("Enter your ElevenLabs API key")
        layout.addWidget(self.api_key_input)
        
        # Info text
        info_label = QLabel("Get your API key from: https://elevenlabs.io")
        info_label.setStyleSheet("color: gray; font-size: 10px;")
        layout.addWidget(info_label)
        
        # Spacer
        layout.addSpacing(20)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        save_button = QPushButton("Save")
        save_button.clicked.connect(self.save_settings)
        button_layout.addWidget(save_button)
        
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def load_settings(self):
        """Load current settings into the dialog"""
        api_key = self.config_manager.get_api_key()
        self.api_key_input.setText(api_key)
    
    def save_settings(self):
        """Save settings from the dialog"""
        api_key = self.api_key_input.text().strip()
        
        if self.config_manager.set_api_key(api_key):
            QMessageBox.information(
                self,
                "Settings Saved",
                "Your settings have been saved successfully!"
            )
            self.accept()
        else:
            QMessageBox.critical(
                self,
                "Error",
                "Failed to save settings. Please try again."
            )


def show_settings_dialog(parent=None):
    """Show the settings dialog"""
    dialog = SettingsDialog(parent)
    return dialog.exec() if hasattr(dialog, 'exec') else dialog.exec_()
