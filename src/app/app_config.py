import os
from PySide6.QtCore import QObject
from services.config_service import ConfigService
from managers.config_manager import ConfigManager

class AppConfig(QObject):
    """Manages application configuration"""
    
    def __init__(self, config=None):
        super().__init__()
        self.config = config or ConfigService()
        self.config_manager = ConfigManager(self.config)
    
    @property
    def directory(self):
        return self.config_manager.directory
    
    @directory.setter
    def directory(self, value):
        self.config_manager.directory = value
    
    @property
    def tmp_path(self):
        return self.config_manager.tmp_path
    