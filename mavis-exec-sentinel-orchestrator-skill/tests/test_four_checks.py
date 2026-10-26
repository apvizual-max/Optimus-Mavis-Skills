import sys
import os
import pytest
from unittest.mock import patch, mock_open

# Add the scripts directory to sys.path to import the module under test
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts"))
)

import four_checks

VALID_TARGET = """model:
  default: MiniMax-M3
  provider: minimax
  base_url: https://api.minimax.io/anthropic
other: True
fallback_providers:
  - provider: minimax
    model: MiniMax-M3
  - provider: minimax
    model: MiniMax-M2.7
  - provider: minimax-oauth
    model: MiniMax-M2.7-highspeed
fallback_model: []
# retired: llama-3.3-70b-instruct:free
"""

INVALID_TARGET = """model:
  default: other-model
  provider: other
  base_url: https://other
"""


def mock_open_file_valid(filepath, *args, **kwargs):
    if filepath == four_checks.TARGET:
        return mock_open(read_data=VALID_TARGET)()
    elif "profiles" in filepath:
        tier = "1M"  # fallback for testing
        for k, v in four_checks.TIERS.items():
            if k in filepath:
                tier = v
        content = f"_context_tier: {tier}\n" + VALID_TARGET
        return mock_open(read_data=content)()
    return mock_open(read_data="")()


def mock_open_file_invalid(filepath, *args, **kwargs):
    if filepath == four_checks.TARGET:
        return mock_open(read_data=INVALID_TARGET)()
    return mock_open(read_data="")()


@pytest.fixture(autouse=True)
def clear_results():
    four_checks.results.clear()
    yield
    four_checks.results.clear()


def test_check1_bytes_size_failure():
    """Test that check1_bytes fails (returns False) when file size is < 100."""
    with patch("os.path.exists", return_value=True):
        with patch("os.path.getsize", return_value=50):
            result = four_checks.check1_bytes()
            assert result is False


def test_check1_bytes_size_success():
    """Test that check1_bytes passes (returns True) when file size is >= 100."""
    with patch("os.path.exists", return_value=True):
        with patch("os.path.getsize", return_value=150):
            with patch("io.open", side_effect=mock_open_file_valid):
                with patch("builtins.print"):
                    result = four_checks.check1_bytes()
                    assert result is True


def test_check1_bytes_valid_content():
    """Test that check1_bytes correctly validates a well-formed configuration."""
    with (
        patch("os.path.exists", return_value=True),
        patch("os.path.getsize", return_value=500),
        patch("io.open", side_effect=mock_open_file_valid),
        patch("builtins.print"),
    ):
        result = four_checks.check1_bytes()
        assert result is True

        # Verify all C1 checks passed
        c1_results = [r for r in four_checks.results if r[0].startswith("C1")]
        assert len(c1_results) > 0
        assert all(r[1] is True for r in c1_results)


def test_check1_bytes_invalid_content():
    """Test that check1_bytes correctly flags an invalid configuration."""
    with (
        patch("os.path.exists", return_value=True),
        patch("os.path.getsize", return_value=500),
        patch("io.open", side_effect=mock_open_file_invalid),
        patch("builtins.print"),
    ):
        result = four_checks.check1_bytes()
        assert (
            result is True
        )  # The function still returns True, but records FAILs in results

        # Verify specific C1 checks failed
        c1_results = {r[0]: r[1] for r in four_checks.results if r[0].startswith("C1")}
        assert c1_results.get("C1 model block") is False
        assert c1_results.get("C1 ladder first") is False
        assert c1_results.get("C1 fallback_model empty") is False
