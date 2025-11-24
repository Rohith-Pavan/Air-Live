#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GoLive Studio - Configuration Module
Handles application settings and configuration
"""

import os
import json
from pathlib import Path

class Config:
    """Application configuration management"""
    
    def __init__(self):
        self.app_name = "GoLive Studio"
        self.version = "1.0.0"
        self.config_dir = self._get_config_dir()
        self.config_file = self.config_dir / "config.json"
        self.default_settings = self._get_default_settings()
        self.settings = self.load_settings()
    
    def _get_config_dir(self):
        """Get platform-specific configuration directory"""
        if os.name == 'nt':  # Windows
            config_dir = Path(os.environ.get('APPDATA', '')) / self.app_name
        else:  # macOS and Linux
            config_dir = Path.home() / '.config' / self.app_name.lower().replace(' ', '_')
        
        # Create directory if it doesn't exist
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir
    
    def _get_default_settings(self):
        """Get default application settings"""
        return {
            "window": {
                "width": 1371,
                "height": 790,
                "x": 100,
                "y": 100
            },
            "recording": {
                "output_format": "mp4",
                "quality": "high",
                "fps": 30,
                "audio_enabled": True
            },
            "streaming": {
                "stream1_enabled": False,
                "stream2_enabled": False,
                "stream1_url": "",
                "stream2_url": "",
                "stream1_key": "",
                "stream2_key": ""
            },
            "audio": {
                "monitor_enabled": True,
                "output_device": "default",
                "input_device": "default",
                "volume": 0.8
            },
            "ui": {
                "theme": "dark",
                "show_tooltips": True,
                "auto_save": True,
                "last_effect": None,
                "overscan": 1.03,
                "preview_fps": 30
            }
        }
    
    def load_settings(self):
        """Load settings from config file"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded_settings = json.load(f)
                # Merge with defaults to ensure all keys exist
                settings = self.default_settings.copy()
                self._deep_update(settings, loaded_settings)
                return settings
            else:
                return self.default_settings.copy()
        except Exception as e:
            print(f"Error loading settings: {e}")
            return self.default_settings.copy()
    
    def save_settings(self):
        """Save current settings to config file"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Error saving settings: {e}")
            return False
    
    def get(self, key_path, default=None):
        """Get setting value using dot notation (e.g., 'window.width')"""
        keys = key_path.split('.')
        value = self.settings
        
        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default
    
    def set(self, key_path, value):
        """Set setting value using dot notation"""
        keys = key_path.split('.')
        setting = self.settings
        
        # Navigate to the parent of the target key
        for key in keys[:-1]:
            if key not in setting:
                setting[key] = {}
            setting = setting[key]
        
        # Set the value
        setting[keys[-1]] = value
    
    def _deep_update(self, base_dict, update_dict):
        """Recursively update nested dictionary"""
        for key, value in update_dict.items():
            if key in base_dict and isinstance(base_dict[key], dict) and isinstance(value, dict):
                self._deep_update(base_dict[key], value)
            else:
                base_dict[key] = value
    
    def reset_to_defaults(self):
        """Reset all settings to default values"""
        self.settings = self.default_settings.copy()
        return self.save_settings()

# Global config instance
app_config = Config()
