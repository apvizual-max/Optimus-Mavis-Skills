"""
check_inbox.py
==============
Scans the Antigravity bridge inbox for pending tasks from Hermes.
Prints a formatted summary of all pending tasks, sorted by priority then mtime.

Usage:
    python check_inbox.py
    python check_inbox.py --full    (show full task content)
"""

import json
import argparse
from pathlib import Path
from datetime import datetime
import concurrent.futures

BRIDGE_ROOT = Path(r"C:\Users\apviz\AppData\Local\hermes\pairing\antigravity")
INBOX = BRIDGE_ROOT / "inbox"
OUTBOX = BRIDGE_ROOT / "outbox"
HISTORY = BRIDGE_ROOT / "history"

PRIORITY_ORDER = {"urgent": 0, "high": 1, "normal": 2, "low": 3}


def fmt_time(iso_str: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_str.replace('Z', '+00:00'))
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except Exception:
        return iso_str


def _read_task(f: Path):
    try:
        return (json.loads(f.read_text(encoding="utf-8")), None)
    except Exception as e:
        return (None, f"  [ERROR] Cannot read {f.name}: {e}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--full', action='store_true', help='Show full task content')
    args = parser.parse_args()

    # Ensure dirs exist
    for d in [INBOX, OUTBOX, HISTORY]:
        d.mkdir(parents=True, exist_ok=True)

    tasks = []
    files = list(INBOX.glob("*.json"))
    if files:
        with concurrent.futures.ProcessPoolExecutor() as executor:
            for task, err in executor.map(_read_task, files, chunksize=50):
                if task is not None:
                    tasks.append(task)
                elif err:
                    print(err)

    if not tasks:
        print("INBOX: Empty — no pending tasks from Hermes.")
        pending_resp = list(OUTBOX.glob("*.json"))
        if pending_resp:
            print(f"\nOUTBOX: {len(pending_resp)} response(s) ready for Hermes to pick up")
        return

    # Sort by priority then by creation time
    tasks.sort(key=lambda t: (PRIORITY_ORDER.get(t.get("priority", "normal"), 2),
                               t.get("created_at", "")))

    print(f"INBOX: {len(tasks)} pending task(s)\n")
    print("-" * 70)

    for task in tasks:
        priority = task.get("priority", "normal").upper()
        task_type = task.get("task_type", "general")
        task_id = task.get("task_id", "unknown")
        caller = task.get("caller", "unknown")
        created = fmt_time(task.get("created_at", ""))
        content = task.get("content", "")
        context = task.get("context", {})

        print(f"[{priority}] {task_id}")
        print(f"  Type    : {task_type}")
        print(f"  From    : {caller}")
        print(f"  Created : {created}")
        if args.full:
            print(f"  Task    : {content}")
            if context:
                print(f"  Context : {json.dumps(context, ensure_ascii=False)}")
        else:
            preview = content[:150] + ("..." if len(content) > 150 else "")
            print(f"  Preview : {preview}")
        print()

    print("-" * 70)
    print(f"\nOutbox: {len(list(OUTBOX.glob('*.json')))} response(s) pending Hermes pickup")
    print(f"History: {len(list(HISTORY.glob('*.json')))} archived tasks")


if __name__ == "__main__":
    main()
