import sys
import os
import pytest
from unittest.mock import patch

# Add the scripts directory to sys.path to import the module under test
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts')))

import four_checks

def test_check1_bytes_size_failure():
    """Test that check1_bytes fails (returns False) when file size is < 100."""
    with patch('os.path.exists', return_value=True):
        with patch('os.path.getsize', return_value=50):
            result = four_checks.check1_bytes()
            assert result is False

def test_check1_bytes_size_success():
    """Test that check1_bytes passes (returns True) when file size is >= 100."""
    with patch('os.path.exists', return_value=True):
        with patch('os.path.getsize', return_value=150):
            # We must also mock io.open and the rest of the function because the function now continues
            with patch('io.open') as mock_io_open:
                mock_io_open.return_value.read.return_value = ""
                with patch('builtins.print'):
                    result = four_checks.check1_bytes()
                    assert result is True
