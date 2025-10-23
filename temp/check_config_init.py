import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from common.config import Config

c = Config()
print(f'last_directory property: "{c.last_directory}"')
print(f'_config dict value: "{c._config["Paths"]["last_directory"]}"')
print(f'Are they the same? {c.last_directory == c._config["Paths"]["last_directory"]}')
