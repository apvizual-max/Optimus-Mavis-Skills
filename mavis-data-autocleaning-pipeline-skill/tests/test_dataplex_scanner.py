import pytest
import sys
import os
import asyncio

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../scripts"))
)

from dataplex_scanner import run_command_async


def test_run_command_async_success():
    """Test successful command execution returns expected output."""
    output = asyncio.run(run_command_async(["echo", "hello"]))
    assert output.strip() == "hello"


def test_run_command_async_failure():
    """Test that a failing command raises a RuntimeError."""
    with pytest.raises(RuntimeError) as exc_info:
        asyncio.run(
            run_command_async(["ls", "/path/to/nonexistent/file/that/should/not/exist"])
        )
    assert "Command failed: ls /path/to/nonexistent/file/that/should/not/exist" in str(
        exc_info.value
    )


def test_run_command_async_command_injection_prevention():
    """
    Test that the command runner properly escapes or avoids shell evaluation
    by passing shell metacharacters as normal string arguments instead of executing them.
    If it were vulnerable to command injection via shell=True, 'ls' might execute.
    With exec, the entire string including semicolons is passed to 'echo'.
    """
    output = asyncio.run(run_command_async(["echo", "hello", ";", "echo", "world"]))
    # If vulnerable to command injection, output would likely contain 'hello' on one line
    # and 'world' on another. If secure, it's just 'hello ; echo world'
    assert "hello ; echo world" in output.strip()
