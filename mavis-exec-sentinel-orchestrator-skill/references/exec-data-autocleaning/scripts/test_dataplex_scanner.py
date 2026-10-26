import pytest
import asyncio
from dataplex_scanner import run_command_async

def test_run_command_async_success():
    """Test that a basic command runs successfully."""
    output = asyncio.run(run_command_async(["echo", "hello"]))
    assert output.strip() == "hello"

def test_run_command_async_failure():
    """Test that a failing command raises RuntimeError."""
    with pytest.raises(RuntimeError) as exc_info:
        asyncio.run(run_command_async(["ls", "/nonexistent_directory_for_test_123"]))
    assert "Command failed: ls /nonexistent_directory_for_test_123" in str(exc_info.value)

def test_run_command_async_no_shell_injection():
    """Test that shell metacharacters are passed as arguments, not interpreted."""
    # If the shell was used, `echo hello; echo injected` would execute both.
    # Without shell (using exec), it just passes `hello; echo injected` to echo.
    output = asyncio.run(run_command_async(["echo", "hello; echo injected"]))
    assert output.strip() == "hello; echo injected"
