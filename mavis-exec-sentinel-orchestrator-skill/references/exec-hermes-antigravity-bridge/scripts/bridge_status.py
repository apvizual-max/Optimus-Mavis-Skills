"""
bridge_status.py
================
Prints current Antigravity bridge queue statistics and health.

Usage:
    python bridge_status.py
    python bridge_status.py --list-inbox   (also show task IDs)
    python bridge_status.py --list-outbox  (also show response IDs)
"""

import json
import argparse
import sys
from pathlib import Path
from datetime import datetime

BRIDGE_ROOT = Path(r"C:\Users\apviz\AppData\Local\hermes\pairing\antigravity")
INBOX = BRIDGE_ROOT / "inbox"
OUTBOX = BRIDGE_ROOT / "outbox"
HISTORY = BRIDGE_ROOT / "history"
STATUS_FILE = BRIDGE_ROOT / "status.json"


def fmt_time(iso_str: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_str.replace('Z', '+00:00'))
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except Exception:
        return iso_str or "unknown"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--list-inbox", action="store_true")
    parser.add_argument("--list-outbox", action="store_true")
    parser.add_argument("--list-history", action="store_true")
    args = parser.parse_args()

    # Ensure dirs exist
    for d in [INBOX, OUTBOX, HISTORY]:
        d.mkdir(parents=True, exist_ok=True)

    inbox_tasks = list(INBOX.glob("*.json"))
    outbox_responses = list(OUTBOX.glob("*.json"))
    history_items = list(HISTORY.glob("*.json"))

    print("╔══════════════════════════════════════════════╗")
    print("║     Antigravity Bridge Status                ║")
    print("╚══════════════════════════════════════════════╝")
    print()
    print("  Bridge:   ACTIVE")
    print(f"  Inbox:    {len(inbox_tasks)} pending task(s)")
    print(f"  Outbox:   {len(outbox_responses)} response(s) awaiting Hermes pickup")
    print(f"  History:  {len(history_items)} archived task(s)")

    if STATUS_FILE.exists():
        try:
            status = json.loads(STATUS_FILE.read_text(encoding="utf-8"))
            updated = fmt_time(status.get("updated_at", ""))
            print(f"  Updated:  {updated}")
        except Exception as e:
            print(f"  Warning: Could not read status file: {e}", file=sys.stderr)

    print()

    if args.list_inbox and inbox_tasks:
        print("── Pending Tasks (inbox) ──────────────────────")
        for f in sorted(inbox_tasks, key=lambda x: x.stat().st_mtime):
            try:
                task = json.loads(f.read_text(encoding="utf-8"))
                priority = task.get("priority", "normal").upper()
                task_type = task.get("task_type", "?")
                created = fmt_time(task.get("created_at", ""))
                content_preview = task.get("content", "")[:80]
                print(f"  [{priority}] {f.stem}")
                print(f"    Type: {task_type} | Created: {created}")
                print(f"    Task: {content_preview}...")
            except Exception as e:
                print(f"  ERROR: {f.name}: {e}")
        print()

    if args.list_outbox and outbox_responses:
        print("── Ready Responses (outbox) ───────────────────")
        for f in sorted(outbox_responses, key=lambda x: x.stat().st_mtime):
            try:
                resp = json.loads(f.read_text(encoding="utf-8"))
                completed = fmt_time(resp.get("completed_at", ""))
                summary = resp.get("summary", "")[:80]
                print(f"  {f.stem}")
                print(f"    Completed: {completed}")
                print(f"    Summary: {summary}...")
            except Exception as e:
                print(f"  ERROR: {f.name}: {e}")
        print()

    if args.list_history and history_items:
        print("── History (last 10) ──────────────────────────")
        for f in sorted(history_items, key=lambda x: x.stat().st_mtime, reverse=True)[:10]:
            try:
                task = json.loads(f.read_text(encoding="utf-8"))
                status = task.get("status", "?")
                completed = fmt_time(task.get("completed_at", ""))
                print(f"  [{status.upper()}] {f.stem} | {completed}")
            except Exception as e:
                print(f"  {f.stem} (Error: {e})", file=sys.stderr)


if __name__ == "__main__":
    main()
