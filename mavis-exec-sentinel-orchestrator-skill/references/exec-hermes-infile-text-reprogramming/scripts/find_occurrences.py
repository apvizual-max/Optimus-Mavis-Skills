"""
find_occurrences.py
===================
Dry-run scanner: finds all occurrences of legacy terms in text files
across the Hermes system. Reports file paths, line numbers, and match counts.
No files are modified.

Usage:
    python find_occurrences.py
    python find_occurrences.py --root "C:\\path\\to\\scan"
    python find_occurrences.py --summary-only
"""

import re
import sys
import argparse
from pathlib import Path
import concurrent.futures

# ── Configuration ─────────────────────────────────────────────────────────────

ROOT_DEFAULT = r"C:\Users\apviz\AppData\Local\hermes"

# Match slash-separated compound FIRST (before individual variants)
SLASH_PATTERNS = [
    re.compile(r'(?<![a-zA-Z0-9_])(CONSTIINTA\s*/\s*CON[ŞS]TIN[ŢT][AĂ])(?![a-zA-Z0-9_])', re.IGNORECASE),
    re.compile(r'(?<![a-zA-Z0-9_])(CON[ŞS]TIN[ŢT][AĂ]\s*/\s*CONSTIINTA)(?![a-zA-Z0-9_])', re.IGNORECASE),
]

# Individual variant patterns
SINGLE_PATTERNS = [
    re.compile(r'(?<![a-zA-Z0-9_])(CON[ŞS]TIN[ŢT][AĂ])(?![a-zA-Z0-9_])', re.IGNORECASE),
    re.compile(r'(?<![a-zA-Z0-9_])(CONSTIINTA)(?![a-zA-Z0-9_])', re.IGNORECASE),
    re.compile(r'(?<![a-zA-Z0-9_])(CONȘTINȚA)(?![a-zA-Z0-9_])'),
]

ALL_PATTERNS = SLASH_PATTERNS + SINGLE_PATTERNS

TEXT_EXTENSIONS = {'.md', '.py', '.json', '.yaml', '.yml', '.txt',
                   '.log', '.vbs', '.cmd', '.ps1', '.sh'}

EXCLUDE_DIRS = {'OGLINDA - CASA', '.git', 'venv', 'node_modules',
                '__pycache__', '.eggs', 'dist', 'build'}


# ── Scanner ───────────────────────────────────────────────────────────────────

def should_exclude(path: Path) -> bool:
    return any(ex in path.parts for ex in EXCLUDE_DIRS)


def scan_file(path: Path):
    """Return list of (line_number, line, match) tuples for this file."""
    hits = []
    try:
        content = path.read_text(encoding='utf-8', errors='replace')
    except Exception:
        return hits

    for i, line in enumerate(content.splitlines(), 1):
        for pat in ALL_PATTERNS:
            if pat.search(line):
                hits.append((i, line.strip(), pat.pattern))
                break  # one hit per line
    return hits


def run(root: Path, summary_only: bool = False):
    total_matches = 0
    total_files = 0
    results = []

    valid_paths = []
    for path in root.rglob('*'):
        if not path.is_file():
            continue
        if should_exclude(path):
            continue
        if path.suffix.lower() not in TEXT_EXTENSIONS:
            continue
        valid_paths.append(path)

    if valid_paths:
        with concurrent.futures.ThreadPoolExecutor() as executor:
            for path, hits in zip(valid_paths, executor.map(scan_file, valid_paths)):
                if hits:
                    total_files += 1
                    total_matches += len(hits)
                    results.append((path, hits))

    if not summary_only:
        for path, hits in sorted(results, key=lambda x: str(x[0])):
            rel = path.relative_to(root) if path.is_relative_to(root) else path
            print(f"\n{rel}  ({len(hits)} match{'es' if len(hits) > 1 else ''})")
            for lineno, line, pat in hits:
                print(f"  L{lineno:4d}: {line[:120]}")

    print(f"\n{'='*60}")
    print(f"Total files with matches : {total_files}")
    print(f"Total match occurrences  : {total_matches}")
    if total_matches == 0:
        print("STATUS: CLEAN — No legacy occurrences found")
    else:
        print("STATUS: MATCHES FOUND — run replace_occurrences.py to fix")
    return total_matches


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', default=ROOT_DEFAULT)
    parser.add_argument('--summary-only', action='store_true')
    args = parser.parse_args()
    count = run(Path(args.root), args.summary_only)
    sys.exit(0 if count == 0 else 1)
