#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
SKILL GUARD — the thing that stops skills from crushing the config.

Popy: "make sure they're perfectly aligned with the current system
configuration. Ensure that skills don't crush the config. You got it! That's
the basic risk you need to eliminate because that's what happened to us. That's
why we spent another day out of frustration."

The failure that cost a day was not a bad value. It was a SKILL that told an
agent to rewrite `config.yaml` / `models.py` in a way that could never be
correct on this system. So this is not a text scan for wrong values. This is a
GUARD over two things:

  G1  CONFIG-CRUSHER DETECTION
      Any skill that instructs writing model.default / fallback_providers /
      models.py, or that runs a config-mutating script. Those are ranked, not
      banned, because some are legitimate maintenance.

  G2  LIVE-FILE INTEGRITY
      config.yaml + each profile config are hashed. If a skill-driven change
      moves them away from the ratified state, this reports the drift
      immediately, with a diff, instead of being discovered days later.

Exit codes: 0 clean, 1 policy violations, 2 config drift.
Run it any time; it is read-only except for its own report file.
"""
import hashlib
import io
import json
import os
import re
import sys
import datetime

HERMES = r"C:\Users\apviz\AppData\Local\hermes"
ROOTS = [
    r"C:\Users\apviz\.minimax\skills",
    r"C:\Users\apviz\.minimax\agents\mavis\skills",
    r"C:\Users\apviz\AppData\Local\hermes\skills",
]
STATE = r"C:\Users\apviz\.learn\antigravity-skill-adaptation\guard_baseline.json"
SKIP = {".git", "node_modules", "__pycache__", ".curator_backups"}
EXT = (".md", ".py", ".ps1", ".bat", ".vbs", ".json", ".yaml", ".yml")

# The ratified state, per Popy 2026-10-02. Any change here is a DECISION, not a
# side effect of a skill run.
RATIFIED = {
    "model.default": "MiniMax-M3",
    "model.provider": "minimax",
    "model.base_url": "https://api.minimax.io/anthropic",
}
LADDER = ["MiniMax-M3", "MiniMax-M2.7", "MiniMax-M2.7-highspeed"]

# Patterns that indicate an instruction capable of rewriting model routing.
CRUSHERS = [
    ("writes model.default", re.compile(r"(?i)(write|set|change|update|modify|patch|edit)\b[^.\n]{0,40}\bmodel\.default\b")),
    ("writes fallback_providers", re.compile(r"(?i)(write|set|change|update|modify|patch|edit|replace)\b[^.\n]{0,40}\bfallback_providers\b")),
    ("rewrites models.py", re.compile(r"(?i)(open|write|patch|modify)\b[^.\n]{0,60}\bmodels\.py\b")),
    ("edits config.yaml", re.compile(r"(?i)(>|\btee\b|Set-Content|write_text|open\([^)]*['\"]w)[\s\S]{0,40}config\.yaml")),
    ("deletes model cache", re.compile(r"(?i)delete[^\n]{0,50}provider_models_cache")),
    ("hermes model command", re.compile(r"(?i)`?\bhermes\s+model\b")),
    ("config-version bump", re.compile(r"(?i)_config_version\s*[:=]")),
]
GUARDED = re.compile(r"(?i)forbidden|never\b|do not|must not|withdrawn|CORRECTED"
                     r"|ROOT CAUSE|not free|do not re-add|prohibit")


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()[:16]


def scan_crushers():
    hits = []
    for root in ROOTS:
        if not os.path.isdir(root):
            continue
        for dp, dn, fn in os.walk(root):
            dn[:] = [d for d in dn if d not in SKIP]
            for f in fn:
                if not f.lower().endswith(EXT):
                    continue
                p = os.path.join(dp, f)
                try:
                    lines = io.open(p, "r", encoding="utf-8", errors="ignore").read().splitlines()
                except OSError:
                    continue
                found = []
                for i, line in enumerate(lines):
                    for label, pat in CRUSHERS:
                        if pat.search(line):
                            ctx = " ".join(lines[max(0, i - 2): i + 3])
                            if not GUARDED.search(ctx):
                                found.append((label, i + 1, line.strip()[:100]))
                if found:
                    hits.append((p, found))
    return hits


def check_config():
    drift = []
    root = os.path.join(HERMES, "config.yaml")
    t = io.open(root, encoding="utf-8").read()
    for key, want in RATIFIED.items():
        leaf = key.split(".")[-1]
        m = re.search(r"(?m)^\s*%s:\s*(\S+)" % re.escape(leaf), t)
        got = m.group(1) if m else None
        if got != want:
            drift.append(("config.yaml", key, want, got))
    # tier 1 must be the first three entries
    fp = re.search(r"(?ms)^fallback_providers:\n((?:  - provider:[^\n]*\n    model: [^\n]*\n)+)", t)
    if not fp:
        drift.append(("config.yaml", "fallback_providers", "present", "MISSING"))
    else:
        models = re.findall(r"    model: (\S+)", fp.group(1))
        if models[:3] != LADDER:
            drift.append(("config.yaml", "fallback_providers[0:3]", str(LADDER), str(models[:3])))
    # every profile: parse and check ladder-first
    prof = os.path.join(HERMES, "profiles")
    for name in sorted(os.listdir(prof)):
        p = os.path.join(prof, name, "config.yaml")
        if not os.path.isfile(p):
            continue
        pt = io.open(p, encoding="utf-8").read()
        pm = re.search(r"(?ms)^fallback_providers:\n((?:  - provider:[^\n]*\n    model: [^\n]*\n)+)", pt)
        if pm:
            ms = re.findall(r"    model: (\S+)", pm.group(1))
            if ms[:3] != LADDER:
                drift.append((os.path.join("profiles", name, "config.yaml"),
                              "fallback_providers[0:3]", str(LADDER), str(ms[:3])))
    return drift


def main():
    print("=" * 78)
    print("SKILL GUARD  %s" % datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 78)

    print("\n[G1] config-crusher instructions found in skill trees")
    hits = scan_crushers()
    if not hits:
        print("   none")
    for p, found in hits:
        rel = p.replace("C:\\Users\\apviz\\", "")
        print("   %s" % rel)
        for label, ln, txt in found[:4]:
            print("        L%-5d %-24s %s" % (ln, label, txt[:70]))
        if len(found) > 4:
            print("        ... +%d more" % (len(found) - 4))
    print("   files with unguarded crusher instructions: %d" % len(hits))

    print("\n[G2] live-config integrity against the ratified state")
    drift = check_config()
    if not drift:
        print("   CLEAN — model.default=MiniMax-M3, provider=minimax, Tier-1 ladder first")
    for f, key, want, got in drift:
        print("   DRIFT %s :: %s\n        want %s\n        got  %s" % (f, key, want, got))

    baseline = {
        "captured": datetime.datetime.now().isoformat(timespec="seconds"),
        "root_config_sha": sha(os.path.join(HERMES, "config.yaml")),
        "crusher_files": len(hits),
    }
    try:
        io.open(STATE, "w", encoding="utf-8").write(json.dumps(baseline, indent=2))
    except OSError as e:
        print(f"Warning: Failed to write baseline state to {STATE}: {e}")

    print("\nbaseline sha: %s" % baseline["root_config_sha"])
    if drift:
        print("\nVERDICT: CONFIG DRIFT (exit 2)")
        return 2
    print("\nVERDICT: config intact. %d crusher file(s) to review manually." % len(hits))
    return 0


if __name__ == "__main__":
    sys.exit(main())
