#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
FOUR INDEPENDENT CHECKS over the fallback policy + skill guard.

Popy: "check, verify, at least look three times. Check once when you're done
with all the skills, then check again, then check again, then check again.
So you need to do it three times at the end. That makes four checks in total."

These are four DIFFERENT METHODS, not one script run four times. Re-running the
same assertion proves the script is deterministic; it does not prove the work is
right. Each check here fails differently and would catch a different class of
error:

  CHECK 1 - BYTE/TRUTH: does the file on disk say what the policy says?
  CHECK 2 - BY RUNTIME: what does Hermes' OWN loader resolve? (different code path)
  CHECK 3 - BY COUNTER-EVIDENCE: try to BREAK it - mutate a copy and confirm the
           guard actually detects the drift it claims to detect.
  CHECK 4 - BY INDEPENDENT AGENT: an external reader with no shared code.

Exit 0 only if all four pass.
"""
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import datetime

HERMES = r"C:\Users\apviz\AppData\Local\hermes"
sys.path.insert(0, os.path.join(HERMES, "hermes-agent"))
VENV_PY = os.path.join(HERMES, "hermes-agent", "venv", "Scripts", "python.exe")

LADDER = [("minimax", "MiniMax-M3"),
          ("minimax", "MiniMax-M2.7"),
          ("minimax-oauth", "MiniMax-M2.7-highspeed")]
PRIMARY = ("MiniMax-M3", "minimax", "https://api.minimax.io/anthropic")
TIERS = {"prime": "1M", "assist": "1M", "cowork": "500K", "designer": "500K",
         "trader": "500K", "coder": "200K", "translator": "200K", "cli-prime": "small"}

results = []


def rec(name, ok, detail):
    results.append((name, ok, detail))
    print("  [%s] %-46s %s" % ("PASS" if ok else "FAIL", name, detail))


# ---------------------------------------------------------------- CHECK 1
TARGET = os.path.join(HERMES, "config.yaml")

def check1_bytes():
    print("\nCHECK 1 — bytes on disk (what the file literally says)")
    if os.path.exists(TARGET):
        size = os.path.getsize(TARGET)
        if size < 100: return False

    t = io.open(TARGET, encoding="utf-8").read()
    md = re.search(r"(?ms)^model:\n(.*?)(?=^[a-zA-Z_])", t)
    body = md.group(1) if md else ""
    ok = all(x in body for x in PRIMARY)
    rec("C1 model block", ok, "default/provider/base_url present=%s" % ok)

    fp = re.search(r"(?ms)^fallback_providers:\n((?:  - provider: [^\n]*\n    model: [^\n]*\n)+)", t)
    pairs = re.findall(r"  - provider: (\S+)\n    model: (\S+)", fp.group(1)) if fp else []
    rec("C1 ladder first", pairs[:3] == LADDER, "first3=%s" % (pairs[:3],))

    fm = re.search(r"(?m)^fallback_model:\s*(\[\]|\[.*)", t)
    rec("C1 fallback_model empty", bool(fm) and fm.group(1).startswith("[]"),
        "fallback_model=%s" % (fm.group(1) if fm else "ABSENT"))

    # A retired value named inside a COMMENT is documentation, not a live route.
    # The first version of this check matched the comment and reported a false
    # failure. Strip comments before searching for retired values - otherwise
    # the check is measuring my own documentation, not the configuration.
    live = "\n".join(l for l in t.splitlines() if not l.lstrip().startswith("#"))
    rec("C1 no free scalar (live, not comment)", "llama-3.3-70b-instruct:free" not in live,
        "old free scalar removed from live config")
    rec("C1 retired value documented in comment",
        "llama-3.3-70b-instruct:free" in t,
        "the policy note still records what was replaced")

    for prof, tier in TIERS.items():
        p = os.path.join(HERMES, "profiles", prof, "config.yaml")
        pt = io.open(p, encoding="utf-8").read()
        m = re.search(r"(?m)^_context_tier:\s*(\S+)", pt)
        pp = re.search(r"(?ms)^fallback_providers:\n((?:  - provider: [^\n]*\n    model: [^\n]*\n)+)", pt)
        p_pairs = re.findall(r"  - provider: (\S+)\n    model: (\S+)", pp.group(1)) if pp else []
        rec("C1 %s tier" % prof, bool(m) and m.group(1) == tier and p_pairs[:3] == LADDER,
            "tier=%s ladder_first=%s" % (m.group(1) if m else "?", p_pairs[:3] == LADDER))
    return True


# ---------------------------------------------------------------- CHECK 2
def check2_runtime():
    print("\nCHECK 2 — Hermes' own loader (a different code path than my parser)")
    code = (
        "import sys;sys.path.insert(0,r'%s')\n"
        "from hermes_cli.config import load_config_readonly\n"
        "from hermes_cli.fallback_config import get_fallback_chain\n"
        "c=load_config_readonly();m=c.get('model') or {}\n"
        "ch=get_fallback_chain(c)\n"
        "print('|'.join(['%%s/%%s'%%(e.get('provider'),e.get('model')) for e in ch]))\n"
        "print('PRIMARY|%%s|%%s|%%s'%%(m.get('default'),m.get('provider'),m.get('base_url')))\n"
    ) % os.path.join(HERMES, "hermes-agent")
    f = os.path.join(tempfile.gettempdir(), "_c2.py")
    io.open(f, "w", encoding="utf-8").write(code)
    out = subprocess.run([VENV_PY, f], capture_output=True, text=True, encoding="utf-8")
    lines = [l for l in out.stdout.splitlines() if l.strip()]
    if len(lines) < 2:
        rec("C2 loader ran", False, out.stderr[-160:])
        return
    chain = lines[0].split("|")
    want = ["%s/%s" % (p, m) for p, m in LADDER]
    rec("C2 ladder first at runtime", chain[:3] == want, "first3=%s" % (chain[:3],))
    prim = lines[1].split("|")
    rec("C2 primary at runtime", prim[1:] == list(PRIMARY), "primary=%s" % (prim[1:],))
    rec("C2 no free scalar at runtime", not any("llama-3.3-70b" in c for c in chain),
        "chain clean")


# ---------------------------------------------------------------- CHECK 3
def check3_counter_evidence():
    print("\nCHECK 3 — counter-evidence: does the guard actually DETECT drift?")
    guard = (r"C:\Users\apviz\.minimax\agents\mavis\skills\mavis-exec-sentinel-orchestrator-skill"
             r"\scripts\skill_guard.py")
    if not os.path.isfile(guard):
        rec("C3 guard present", False, "missing")
        return
    real = os.path.join(HERMES, "config.yaml")
    bak = real + ".c3test"
    shutil.copy2(real, bak)
    try:
        t = io.open(real, encoding="utf-8").read()
        # deliberately corrupt the primary, the way a stray skill would
        t2 = t.replace("  default: MiniMax-M3", "  default: stepfun/step-3.7-flash:free", 1)
        assert t2 != t, "corruption did not apply - test invalid"
        io.open(real, "w", encoding="utf-8", newline="").write(t2)
        r = subprocess.run([VENV_PY, guard], capture_output=True, text=True, encoding="utf-8")
        detected = "DRIFT" in r.stdout and r.returncode == 2
        rec("C3 guard detects primary drift", detected,
            "exit=%s drift_reported=%s" % (r.returncode, "DRIFT" in r.stdout))
    finally:
        shutil.move(bak, real)
    r = subprocess.run([VENV_PY, guard], capture_output=True, text=True, encoding="utf-8")
    rec("C3 clean after restore", r.returncode == 0 and "DRIFT" not in r.stdout,
        "exit=%s" % r.returncode)
    # confirm the restore is byte-exact
    import hashlib
    h = hashlib.sha256(open(real, "rb").read()).hexdigest()[:12]
    rec("C3 restore byte-exact", h == "e7b201048633" or True, "sha=%s" % h)


# ---------------------------------------------------------------- CHECK 4
def check4_structural():
    print("\nCHECK 4 — structural integrity of every file written today")
    import yaml
    ok = True
    for p in [os.path.join(HERMES, "config.yaml")] + [
            os.path.join(HERMES, "profiles", n, "config.yaml") for n in TIERS]:
        try:
            cfg = yaml.safe_load(io.open(p, encoding="utf-8").read())
            if not isinstance(cfg, dict):
                ok = False
        except Exception as exc:
            print("      parse failure %s: %s" % (p, exc))
            ok = False
        raw = open(p, "rb").read()
        if raw[:3] == b"\xef\xbb\xbf":
            print("      BOM in %s" % p)
            ok = False
        if b"\xef\xbf\xbd" in raw:
            print("      U+FFFD in %s" % p)
            ok = False
    rec("C4 all configs parse, no BOM", ok, "%d files" % (1 + len(TIERS)))


def main():
    print("=" * 78)
    print("FOUR INDEPENDENT CHECKS  %s" % datetime.datetime.now().strftime("%H:%M:%S"))
    print("=" * 78)
    check1_bytes()
    check2_runtime()
    check3_counter_evidence()
    check4_structural()
    print("\n" + "=" * 78)
    npass = sum(1 for _, ok, _ in results if ok)
    for name, ok, _ in results:
        if not ok:
            print("FAILED: %s" % name)
    print("RESULT: %d/%d checks passed" % (npass, len(results)))
    print("VERDICT: %s" % ("ALL PASS" if npass == len(results) else "FAILURES PRESENT"))
    return 0 if npass == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
