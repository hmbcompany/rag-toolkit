"""
Configuration management for RAG Toolkit.

Handles loading configuration from ~/.ragtk.yaml and environment variables.
"""

import os
import yaml
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class RAGToolkitConfig:
    """RAG Toolkit configuration."""
    api_url: str = "http://localhost:8000"
    project: str = "default"
    token: Optional[str] = None
    created: Optional[str] = None
    version: str = "0.2.0"


class ConfigManager:
    """Manages RAG Toolkit configuration."""
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize config manager.
        
        Args:
            config_path: Path to config file. Defaults to ~/.ragtk.yaml
        """
        self.config_path = config_path or str(Path.home() / ".ragtk.yaml")
        self._config: Optional[RAGToolkitConfig] = None
    
    def load_config(self) -> RAGToolkitConfig:
        """Load configuration from file and environment variables.
        
        Precedence:
        1. Environment variables (highest)
        2. Config file
        3. Defaults (lowest)
        """
        if self._config:
            return self._config
            
        # Start with defaults
        config_data = {
            "api_url": "http://localhost:8000",
            "project": "default",
            "token": None,
            "created": None,
            "version": "0.2.0"
        }
        
        # Load from config file if exists
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    file_config = yaml.safe_load(f) or {}
                    config_data.update(file_config)
            except Exception as e:
                print(f"Warning: Could not load config file {self.config_path}: {e}")
        
        # Override with environment variables
        env_overrides = {
            "api_url": os.getenv("RAGTOOLKIT_API_URL"),
            "project": os.getenv("RAGTOOLKIT_PROJECT"),
            "token": os.getenv("RAGTOOLKIT_TOKEN") or os.getenv("RAGTOOLKIT_API_KEY"),
        }
        
        for key, value in env_overrides.items():
            if value is not None:
                config_data[key] = value
        
        self._config = RAGToolkitConfig(**config_data)
        return self._config
    
    def save_config(self, config: RAGToolkitConfig) -> None:
        """Save configuration to file.
        
        Args:
            config: Configuration to save
        """
        config_dict = {
            "api_url": config.api_url,
            "project": config.project,
            "token": config.token,
            "created": config.created,
            "version": config.version
        }
        
        # Ensure config directory exists
        config_dir = Path(self.config_path).parent
        config_dir.mkdir(parents=True, exist_ok=True)
        
        with open(self.config_path, 'w') as f:
            yaml.dump(config_dict, f, default_flow_style=False, sort_keys=False)
    
    def update_config(self, **kwargs) -> RAGToolkitConfig:
        """Update configuration with new values.
        
        Args:
            **kwargs: Configuration fields to update
            
        Returns:
            Updated configuration
        """
        config = self.load_config()
        
        for key, value in kwargs.items():
            if hasattr(config, key):
                setattr(config, key, value)
        
        self.save_config(config)
        self._config = None  # Force reload
        return self.load_config()
    
    def update_project(self, project: str) -> RAGToolkitConfig:
        """Update the project name.
        
        Args:
            project: New project name
            
        Returns:
            Updated configuration
        """
        return self.update_config(project=project)


# Global config manager instance
_config_manager = ConfigManager()


def get_config() -> RAGToolkitConfig:
    """Get the current configuration."""
    return _config_manager.load_config()


def update_config(**kwargs) -> RAGToolkitConfig:
    """Update the configuration."""
    return _config_manager.update_config(**kwargs)


def configure(api_url: Optional[str] = None, 
              project: Optional[str] = None,
              token: Optional[str] = None) -> RAGToolkitConfig:
    """Configure RAG Toolkit.
    
    Args:
        api_url: RAG Toolkit API URL
        project: Project name
        token: API token
        
    Returns:
        Updated configuration
    """
    updates = {}
    if api_url is not None:
        updates["api_url"] = api_url
    if project is not None:
        updates["project"] = project
    if token is not None:
        updates["token"] = token
    
    return update_config(**updates) 