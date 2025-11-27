import configparser
import logging
import time

from common.config import Config


def _write_general_setting(config_path: str, key: str, value: str) -> None:
    parser = configparser.ConfigParser()
    parser.read(config_path, encoding="utf-8")
    if not parser.has_section("General"):
        parser.add_section("General")
    parser.set("General", key, value)
    with open(config_path, "w", encoding="utf-8") as handle:
        parser.write(handle)


def test_refresh_if_changed_detects_new_values(tmp_path):
    config_path = tmp_path / "config.ini"
    cfg = Config(custom_config_path=str(config_path))
    assert cfg.log_level == logging.INFO

    time.sleep(1.1)  # Ensure filesystem mtime resolution updates
    _write_general_setting(str(config_path), "log_level", "DEBUG")

    reloaded = cfg.refresh_if_changed()

    assert reloaded is True
    assert cfg.log_level == logging.DEBUG
    assert cfg.log_level_str == "DEBUG"


def test_refresh_if_changed_noop_when_unchanged(tmp_path):
    config_path = tmp_path / "config.ini"
    cfg = Config(custom_config_path=str(config_path))

    assert cfg.refresh_if_changed() is False
