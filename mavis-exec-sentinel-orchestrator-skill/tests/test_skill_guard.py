import pytest
import os
import sys
from unittest.mock import patch, mock_open

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts')))
import skill_guard

# Example config that is fully valid
VALID_CONFIG = """
model:
  default: MiniMax-M3
  provider: minimax
  base_url: https://api.minimax.io/anthropic

fallback_providers:
  - provider: minimax
    model: MiniMax-M3
  - provider: minimax
    model: MiniMax-M2.7
  - provider: minimax
    model: MiniMax-M2.7-highspeed
  - provider: openai
    model: gpt-4
"""

INVALID_CONFIG_RATIFIED = """
model:
  default: MiniMax-M2.7 # DRIFT
  provider: minimax
  base_url: https://api.minimax.io/anthropic

fallback_providers:
  - provider: minimax
    model: MiniMax-M3
  - provider: minimax
    model: MiniMax-M2.7
  - provider: minimax
    model: MiniMax-M2.7-highspeed
"""

INVALID_CONFIG_MISSING_FALLBACK = """
model:
  default: MiniMax-M3
  provider: minimax
  base_url: https://api.minimax.io/anthropic
"""

INVALID_CONFIG_LADDER_ORDER = """
model:
  default: MiniMax-M3
  provider: minimax
  base_url: https://api.minimax.io/anthropic

fallback_providers:
  - provider: minimax
    model: MiniMax-M2.7
  - provider: minimax
    model: MiniMax-M3
  - provider: minimax
    model: MiniMax-M2.7-highspeed
"""

@patch("skill_guard.os.listdir")
@patch("skill_guard.os.path.isfile")
@patch("skill_guard.io.open")
def test_check_config_no_drift(mock_open_file, mock_isfile, mock_listdir):
    mock_open_file.return_value.read.return_value = VALID_CONFIG
    mock_listdir.return_value = []
    mock_isfile.return_value = False

    drift = skill_guard.check_config()
    assert not drift, f"Expected no drift, got: {drift}"

@patch("skill_guard.os.listdir")
@patch("skill_guard.os.path.isfile")
@patch("skill_guard.io.open")
def test_check_config_drift_ratified(mock_open_file, mock_isfile, mock_listdir):
    mock_open_file.return_value.read.return_value = INVALID_CONFIG_RATIFIED
    mock_listdir.return_value = []
    mock_isfile.return_value = False

    drift = skill_guard.check_config()
    assert len(drift) == 1
    assert drift[0] == ("config.yaml", "model.default", "MiniMax-M3", "MiniMax-M2.7")

@patch("skill_guard.os.listdir")
@patch("skill_guard.os.path.isfile")
@patch("skill_guard.io.open")
def test_check_config_drift_missing_fallback(mock_open_file, mock_isfile, mock_listdir):
    mock_open_file.return_value.read.return_value = INVALID_CONFIG_MISSING_FALLBACK
    mock_listdir.return_value = []
    mock_isfile.return_value = False

    drift = skill_guard.check_config()
    assert len(drift) == 1
    assert drift[0] == ("config.yaml", "fallback_providers", "present", "MISSING")

@patch("skill_guard.os.listdir")
@patch("skill_guard.os.path.isfile")
@patch("skill_guard.io.open")
def test_check_config_drift_ladder_order(mock_open_file, mock_isfile, mock_listdir):
    mock_open_file.return_value.read.return_value = INVALID_CONFIG_LADDER_ORDER
    mock_listdir.return_value = []
    mock_isfile.return_value = False

    drift = skill_guard.check_config()
    assert len(drift) == 1
    assert drift[0][0] == "config.yaml"
    assert drift[0][1] == "fallback_providers[0:3]"
    assert drift[0][2] == str(["MiniMax-M3", "MiniMax-M2.7", "MiniMax-M2.7-highspeed"])
    assert drift[0][3] == str(["MiniMax-M2.7", "MiniMax-M3", "MiniMax-M2.7-highspeed"])

@patch("skill_guard.os.listdir")
@patch("skill_guard.os.path.isfile")
def test_check_config_profiles(mock_isfile, mock_listdir):
    mock_listdir.return_value = ["test_profile"]
    mock_isfile.return_value = True

    def mock_open_side_effect(path, *args, **kwargs):
        m = mock_open()
        if "profiles" in path:
            m.return_value.read.return_value = INVALID_CONFIG_LADDER_ORDER
        else:
            m.return_value.read.return_value = VALID_CONFIG
        return m()

    with patch("skill_guard.io.open", side_effect=mock_open_side_effect):
        drift = skill_guard.check_config()
        assert len(drift) == 1
        assert drift[0][0] == os.path.join("profiles", "test_profile", "config.yaml")
        assert drift[0][1] == "fallback_providers[0:3]"
