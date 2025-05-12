import os
from services.config_service import ConfigService
from utils import files


class ConfigManager:
    def __init__(self, config: ConfigService):
        self.config = config
        self._directory = config.default_directory
        self._tmp_path = files.generate_directory_hash(self._directory)

    @property
    def directory(self):
        return self._directory

    @directory.setter
    def directory(self, value: str):
        self._directory = value
        path_hash = files.generate_directory_hash(value)
        self._tmp_path = os.path.join(self.config.tmp_root, path_hash)

    @property
    def tmp_path(self):
        return self._tmp_path
