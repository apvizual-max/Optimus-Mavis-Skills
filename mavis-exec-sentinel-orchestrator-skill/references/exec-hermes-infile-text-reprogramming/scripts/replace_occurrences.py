"""
replace_occurrences.py
======================
Case-aware bulk replacement of legacy terms across all text files.
Always run find_occurrences.py --dry-run FIRST to preview matches.

Usage:
    python replace_occurrences.py --dry-run    (preview only)
    python replace_occurrences.py --apply      (execute changes)

CRITICAL RULES:
  1. Match slash-separated compound variants BEFORE individual variants
  2. Use custom word-boundary regex (NOT \b) to handle Unicode + underscores
  3. Preserve case: UPPER→UPPER, Title→Title, lower→lower
"""

import re
import argparse
from pathlib import Path

# ── Configuration ─────────────────────────────────────────────────────────────

ROOT_DEFAULT = r"C:\Users\apviz\AppData\Local\hermes"
CANONICAL = "CONSTINTA"

# IMPORTANT: slash-separated compound must come FIRST
REPLACEMENT_MAP = [
    # Compound slash-separated forms → single canonical term
    (re.compile(r'(?<![a-zA-Z0-9_])(CONSTIINTA\s*/\s*CON[ŞS]TIN[ŢT][AĂ])(?![a-zA-Z0-9_])', re.IGNORECASE), CANONICAL),
    (re.compile(r'(?<![a-zA-Z0-9_])(CON[ŞS]TIN[ŢT][AĂ]\s*/\s*CONSTIINTA)(?![a-zA-Z0-9_])', re.IGNORECASE), CANONICAL),
    # Individual diacritic/double-i variants
    (re.compile(r'(?<![a-zA-Z0-9_])(CON[ŞS]TIN[ŢT][AĂ])(?![a-zA-Z0-9_])', re.IGNORECASE), CANONICAL),
    (re.compile(r'(?<![a-zA-Z0-9_])(CONSTIINTA)(?![a-zA-Z0-9_])', re.IGNORECASE), CANONICAL),
    (re.compile(r'(?<![a-zA-Z0-9_])(CONȘTINȚA)(?![a-zA-Z0-9_])'), CANONICAL),
]

TEXT_EXTENSIONS = {'.md', '.py', '.json', '.yaml', '.yml', '.txt',
                   '.log', '.vbs', '.cmd', '.ps1', '.sh'}

EXCLUDE_DIRS = {'OGLINDA - CASA', '.git', 'venv', 'node_modules',
                '__pycache__', '.eggs', 'dist', 'build'}


# ── Case preservation ─────────────────────────────────────────────────────────

def preserve_case(match_text: str, replacement: str) -> str:
    """Return replacement with same case as match_text."""
    if match_text.isupper():
        return replacement.upper()
    elif match_text[0].isupper() and match_text[1:].islower():
        return replacement.capitalize()
    elif match_text.islower():
        return replacement.lower()
    else:
        return replacement  # mixed/special case → use canonical as-is


def apply_replacement(content: str, pattern: re.Pattern, replacement: str) -> tuple[str, int]:
    """Apply case-preserving replacement, return (new_content, count)."""
    count = 0

    def repl_func(m):
        nonlocal count
        count += 1
        return preserve_case(m.group(0), replacement)

    new_content = pattern.sub(repl_func, content)
    return new_content, count


# ── File processor ────────────────────────────────────────────────────────────

def process_file(path: Path, dry_run: bool = True) -> int:
    try:
        original = path.read_text(encoding='utf-8', errors='replace')
    except Exception as e:
        print(f"  ERROR reading {path}: {e}")
        return 0

    content = original
    total_replacements = 0

    for pattern, replacement in REPLACEMENT_MAP:
        content, count = apply_replacement(content, pattern, replacement)
        total_replacements += count

    if total_replacements > 0:
        print(f"  [{total_replacements} replacements] {path}")
        if not dry_run:
            path.write_text(content, encoding='utf-8')

    return total_replacements


def run(root: Path, dry_run: bool = True):
    total_files = 0
    total_replacements = 0

    if dry_run:
        print("DRY RUN — no files will be modified\n")
    else:
        print(f"APPLYING changes to: {root}\n")

    for path in sorted(root.rglob('*')):
        if not path.is_file():
            continue
        if any(ex in path.parts for ex in EXCLUDE_DIRS):
            continue
        if path.suffix.lower() not in TEXT_EXTENSIONS:
            continue

        count = process_file(path, dry_run)
        if count > 0:
            total_files += 1
            total_replacements += count

    print(f"\n{'='*60}")
    print(f"Files modified  : {total_files}")
    print(f"Total replacements: {total_replacements}")
    if dry_run:
        print("\n[DRY RUN] Run with --apply to execute changes.")
    else:
        print("\n[DONE] Run find_occurrences.py to verify count = 0.")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', default=ROOT_DEFAULT)
    parser.add_argument('--dry-run', action='store_true', default=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    dry_run = not args.apply
    run(Path(args.root), dry_run=dry_run)
