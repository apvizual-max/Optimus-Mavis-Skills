"""
test_mcp_jsonrpc.py
===================
Universal MCP server JSON-RPC test harness.
Tests: initialize → notifications/initialized → tools/list → optional tool call

Usage:
    python test_mcp_jsonrpc.py
    python test_mcp_jsonrpc.py --server agent-browser
    python test_mcp_jsonrpc.py --server antigravity-bridge

Tested servers:
    - agent-browser (npm, expects 64 tools)
    - antigravity-bridge (Python, expects 9 tools)
    - any custom Python MCP server
"""

import subprocess
import json
import sys
import argparse
from typing import Optional

PYTHON = r"C:\Users\apviz\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe"
AB_CMD = r"C:\Users\apviz\AppData\Local\hermes\node\agent-browser.cmd"

KNOWN_SERVERS = {
    "agent-browser": {
        "cmd": [AB_CMD, "mcp", "--tools", "all"],
        "min_tools": 60,
        "spot_check_tool": None,
    },
    "antigravity-bridge": {
        "cmd": [PYTHON, "-m", "antigravity_bridge.server"],
        "min_tools": 9,
        "spot_check_tool": "ag_get_status",
    },
    "optimus-orchestrator": {
        "cmd": [PYTHON, "-m", "optimus_orchestrator.server"],
        "min_tools": 1,
        "spot_check_tool": None,
    },
    "session-replay": {
        "cmd": [PYTHON, "-m", "session_replay.server"],
        "min_tools": 1,
        "spot_check_tool": None,
    },
}


def send_rpc(proc, method: str, params: dict, id_: int = 1) -> dict:
    msg = json.dumps({"jsonrpc": "2.0", "id": id_, "method": method, "params": params}) + "\n"
    proc.stdin.write(msg.encode())
    proc.stdin.flush()
    raw = proc.stdout.readline()
    return json.loads(raw)


def run_test_server(name: str, cmd: list, min_tools: int = 1,
                spot_check_tool: Optional[str] = None) -> bool:
    print(f"\n{'='*50}")
    print(f"Testing: {name}")
    print(f"Command: {' '.join(cmd)}")
    print()

    try:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Stage 1: Initialize
        resp = send_rpc(proc, "initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "hermes-verify", "version": "1.0.0"}
        }, id_=1)
        assert "result" in resp, f"Init failed: {resp}"
        server_info = resp["result"].get("serverInfo", {})
        print(f"  INIT:   OK — server={server_info.get('name')} v{server_info.get('version')}")

        # Stage 2: Initialized notification
        proc.stdin.write(b'{"jsonrpc":"2.0","method":"notifications/initialized","params":{}}\n')
        proc.stdin.flush()

        # Stage 3: tools/list
        resp = send_rpc(proc, "tools/list", {}, id_=2)
        assert "result" in resp, f"tools/list failed: {resp}"
        tools = resp["result"].get("tools", [])
        assert len(tools) >= min_tools, f"Expected >={min_tools} tools, got {len(tools)}"
        print(f"  TOOLS:  OK — {len(tools)} tools returned")
        print(f"  NAMES:  {', '.join(t['name'] for t in tools[:5])}{'...' if len(tools) > 5 else ''}")

        # Stage 4: Optional spot-check tool call
        if spot_check_tool:
            resp = send_rpc(proc, "tools/call", {
                "name": spot_check_tool, "arguments": {}
            }, id_=3)
            assert "result" in resp, f"Tool call failed: {resp}"
            content = resp["result"].get("content", [{}])
            text = content[0].get("text", "") if content else ""
            print(f"  CALL:   OK — {spot_check_tool}() returned {len(text)} chars")

        proc.terminate()
        proc.wait(timeout=5)
        print(f"  RESULT: PASSED ✓")
        return True

    except Exception as e:
        print(f"  RESULT: FAILED ✗ — {e}")
        try:
            proc.terminate()
        except Exception:
            pass
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--server', choices=list(KNOWN_SERVERS.keys()) + ['all'],
                        default='all', help='Which server(s) to test')
    args = parser.parse_args()

    servers_to_test = (
        KNOWN_SERVERS.items() if args.server == 'all'
        else [(args.server, KNOWN_SERVERS[args.server])]
    )

    results = {}
    for name, config in servers_to_test:
        results[name] = run_test_server(
            name, config["cmd"],
            min_tools=config["min_tools"],
            spot_check_tool=config.get("spot_check_tool")
        )

    print(f"\n{'='*50}")
    print("SUMMARY:")
    passed = sum(1 for r in results.values() if r)
    for name, ok in results.items():
        print(f"  {'PASS' if ok else 'FAIL'}: {name}")
    print(f"\n{passed}/{len(results)} servers passed")
    sys.exit(0 if all(results.values()) else 1)


if __name__ == '__main__':
    main()
