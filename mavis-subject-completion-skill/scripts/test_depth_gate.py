"""test_depth_gate.py -- proves depth_gate.py DISCRIMINATES.

A gate that always returns PASS is decoration. A gate that always returns FAIL is
noise. Both look identical to "the script runs". The only evidence either is worth
is that a specific, named defect produces a specific, named failure, and that
removing that defect restores the verdict.

This suite is built around three questions:

  T1 CAN IT PASS?          at least one well-formed record must yield PASS/0
  T2 DOES IT CATCH?        every rule must have a record that fails ONLY it
  T3 IS IT SENSITIVE?      flipping one field must flip the verdict both ways

Plus T4 (permutation) and T5 (typing/shape abuse) which are the cases that
actually broke during authoring.

    python test_depth_gate.py
    exit 0 = suite passed, 1 = suite found a defect in the gate
"""
from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
GATE = os.path.join(HERE, "depth_gate.py")

sys.path.insert(0, HERE)
import depth_gate  # noqa: E402

# --------------------------------------------------------------------------
# The reference PASS record. Every failing case below is a copy of this with
# exactly one field changed -- that is what makes "fails only R1" meaningful.
# --------------------------------------------------------------------------
PASS_RECORD = {
    "subject": "A2A and relay exposed per profile in the Hermes gateway",
    "subject_restated": (
        "The operator asked for A2A and relay per profile in the Hermes gateway. "
        "That is now A2A and relay per profile in the Hermes gateway: each of the 9 "
        "profiles binds its own A2A_PORT and advertises on the card."
    ),
    "claim": "Every profile serves its own A2A port and its own relay endpoint",
    "evidence": (
        "9 processes bound to 9 distinct A2A ports; the agent.json card lists 9 "
        "served agents; per-profile /health returns 200 for all 9"
    ),
    "evidence_is_about": "subject",
    "fix_number_for_symptom": 1,
    "depth_rung": 4,
    "independent_evidence": True,
    "instrument_built_by_me": False,
}

# Every rule the gate can report, and the field(s) that alone should break it.
# Most are single-field. "R2 permanence claim" is inherently RELATIONAL -- asserting
# permanence is only a violation when the depth rung does not support it -- so it
# takes a coordinated pair. That is the rule's nature, not a test convenience.
ONE_FIELD_BREAKS = {
    "R1 plaster test": {"fix_number_for_symptom": 2},
    "R2 depth ladder": {"depth_rung": 2},
    "R3 escape test": {"evidence_is_about": "proxy"},
    "R4 independent evidence": {"independent_evidence": False},
    "R4 instrument independence": {"instrument_built_by_me": True},
    "R4 evidence substance": {"evidence": "verified"},
    "R2 permanence claim": {
        "claim": "The launcher lock is fixed and will not recur",
        "depth_rung": 3,          # rung 4 would make the claim TRUE, not an overclaim
    },
    "R3 subject restatement": {"subject_restated": "Everything is working fine now."},
}


def mutate(**kw):
    r = copy.deepcopy(PASS_RECORD)
    r.update(kw)
    return r


def run_gate_via_cli(rec):
    """Exercise the real CLI path: argv parsing, file IO, exit code, stdout."""
    fd, path = tempfile.mkstemp(suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(rec, fh, ensure_ascii=False)
        proc = subprocess.run(
            [sys.executable, GATE, path],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        return proc.returncode, proc.stdout or ""
    finally:
        os.unlink(path)


RESULTS = []


def record(name, ok, detail=""):
    RESULTS.append((name, ok, detail))
    print("  %s  %-52s %s" % ("PASS" if ok else "FAIL", name, detail))


# ==========================================================================
# T1 -- can it pass at all?
# ==========================================================================
def t1_can_pass():
    print("\nT1  CAN IT PASS?")
    verdict, rows = depth_gate.check(copy.deepcopy(PASS_RECORD))
    record("T1.1 in-process PASS on a well-formed record", verdict == "PASS", "verdict=%s" % verdict)
    failed = [r for r, ok, _ in rows if not ok]
    record("T1.2 all 8 rules pass on that record", not failed, "failed=%s" % (failed or "none"))
    record("T1.3 exactly 8 rules are evaluated", len(rows) == 8, "n=%d" % len(rows))

    code, out = run_gate_via_cli(PASS_RECORD)
    record("T1.4 CLI exit code 0 on PASS", code == 0, "exit=%d" % code)
    record("T1.5 CLI prints VERDICT: PASS", "VERDICT: PASS" in out, "")
    record("T1.6 CLI prints all 8 rule lines", out.count("PASS") >= 9, "PASS lines=%d" % out.count("PASS"))

    # A gate that cannot pass is noise, not a gate. A gate that cannot fail is a
    # rubber stamp. Both are documented failures rather than silent successes.
    record("T1.7 gate is neither always-FAIL nor always-PASS",
           verdict == "PASS" and len(ONE_FIELD_BREAKS) > 0, "")


# ==========================================================================
# T2 -- does each rule actually catch its own defect?
# ==========================================================================
def t2_each_rule_catches():
    print("\nT2  DOES IT CATCH?  (one field changed, exactly one rule must fail)")
    for rule, changes in ONE_FIELD_BREAKS.items():
        verdict, rows = depth_gate.check(mutate(**changes))
        failed = [r for r, ok, _ in rows if not ok]
        record(
            "T2 %s" % rule,
            verdict == "FAIL" and failed == [rule],
            "verdict=%s failed=%s" % (verdict, failed),
        )

    # Each of the above must also fail through the real CLI with exit 1.
    for rule, changes in ONE_FIELD_BREAKS.items():
        code, out = run_gate_via_cli(mutate(**changes))
        record(
            "T2 CLI %s" % rule,
            code == 1 and "VERDICT: FAIL" in out,
            "exit=%d" % code,
        )

    # The relational rule must ALSO pass when the rung genuinely supports the
    # claim -- otherwise the test above would be satisfied by a blanket ban.
    verdict, _ = depth_gate.check(mutate(
        claim="The launcher lock is fixed and will not recur", depth_rung=4))
    record("T2 permanence claim allowed when rung 4 supports it",
           verdict == "PASS", "verdict=%s" % verdict)


# ==========================================================================
# T3 -- is it sensitive?  flipping one field must flip the verdict BOTH ways
# ==========================================================================
def t3_sensitive():
    print("\nT3  IS IT SENSITIVE?  (both directions, per field)")
    for field, bad_value in [
        ("fix_number_for_symptom", 2),
        ("depth_rung", 2),
        ("evidence_is_about", "proxy"),
        ("independent_evidence", False),
        ("instrument_built_by_me", True),
    ]:
        good, _ = depth_gate.check(mutate(**{field: good_value_for(field)}))
        bad, _ = depth_gate.check(mutate(**{field: bad_value}))
        record(
            "T3 %s flips verdict" % field,
            good == "PASS" and bad == "FAIL",
            "good=%s bad=%s" % (good, bad),
        )


def good_value_for(field):
    return {
        "fix_number_for_symptom": 1,
        "depth_rung": 4,
        "evidence_is_about": "subject",
        "independent_evidence": True,
        "instrument_built_by_me": False,
    }[field]


# ==========================================================================
# T4 -- permutation: ALL defects at once must still be reported, not short-
#       circuited to the first one.  A gate that reports one failure and stops
#       makes the operator fix one, re-run, and discover the next.
# ==========================================================================
def t4_reports_every_failure():
    print("\nT4  DOES IT REPORT EVERY FAILURE?")
    rec = mutate(
        fix_number_for_symptom=4,
        depth_rung=1,
        evidence_is_about="proxy",
        independent_evidence=False,
        instrument_built_by_me=True,
        claim="fixed permanently, will never happen again",
        subject_restated="done",
        evidence="",
    )
    verdict, rows = depth_gate.check(rec)
    failed = [r for r, ok, _ in rows if not ok]
    record("T4.1 verdict FAIL", verdict == "FAIL", "verdict=%s" % verdict)
    record("T4.2 all 8 rules reported as failing", len(failed) == 8, "n=%d %s" % (len(failed), failed))

    code, out = run_gate_via_cli(rec)
    record("T4.3 CLI exit 1", code == 1, "exit=%d" % code)
    record("T4.4 CLI names every failing rule",
           all(r in out for r in failed), "")
    record("T4.5 CLI states a fail is not a formality",
           "not a formality" in out, "")


# ==========================================================================
# T5 -- shape abuse.  These are the cases that make a gate lie: it must not
#       pass a record that is well-formed JSON but says nothing.
# ==========================================================================
def t5_shape_abuse():
    print("\nT5  SHAPE ABUSE  (well-formed JSON, empty or hostile content)")

    code, out = run_gate_via_cli({"subject": "x"})
    record("T5.1 missing fields -> INCOMPLETE/2", code == 2 and "INCOMPLETE" in out, "exit=%d" % code)
    record("T5.2 INCOMPLETE names the missing fields", "fix_number_for_symptom" in out, "")

    code, out = run_gate_via_cli({})
    record("T5.3 empty record -> 2, not a crash", code == 2, "exit=%d" % code)

    # The hole this test exists for: an empty subject made subj[:24] == "" and
    # "" in anything is True, so a contentless subject could pass R3 no matter
    # what the restatement said. Paired with a CONTENTFUL restatement, which is
    # the case that actually slipped through the first run.
    rec = mutate(subject="", subject_restated="All nine profiles are serving now")
    verdict, rows = depth_gate.check(rec)
    r3 = [ok for r, ok, _ in rows if r == "R3 subject restatement"][0]
    record("T5.4 empty subject cannot satisfy R3", r3 is False, "R3=%s verdict=%s" % (r3, verdict))

    # Empty subject AND empty restatement, for completeness.
    rec = mutate(subject="", subject_restated="   ")
    verdict, rows = depth_gate.check(rec)
    r3 = [ok for r, ok, _ in rows if r == "R3 subject restatement"][0]
    record("T5.4b empty subject + empty restatement", r3 is False, "R3=%s" % r3)

    # A one-character subject must not let a vacuous substring match through.
    rec = mutate(subject="x", subject_restated="y zzzz")
    verdict, rows = depth_gate.check(rec)
    r3 = [ok for r, ok, _ in rows if r == "R3 subject restatement"][0]
    record("T5.5 1-char subject cannot satisfy R3", r3 is False, "R3=%s" % r3)

    # Type abuse: JSON lets you write anything. None of these may crash.
    for label, kw in [
        ("depth_rung as string", {"depth_rung": "4"}),
        ("depth_rung as bool", {"depth_rung": True}),
        ("depth_rung as null", {"depth_rung": None}),
        ("fix_number as string", {"fix_number_for_symptom": "1"}),
        ("fix_number as float", {"fix_number_for_symptom": 1.9}),
        ("evidence_is_about as Subject", {"evidence_is_about": "Subject"}),
        ("independent as 1", {"independent_evidence": 1}),
        ("claim as list", {"claim": ["fixed", "permanently"]}),
    ]:
        try:
            verdict, _ = depth_gate.check(mutate(**kw))
            code, _out = run_gate_via_cli(mutate(**kw))
            record("T5.6 no crash: %s" % label, isinstance(verdict, str) and code in (0, 1, 2),
                   "verdict=%s exit=%d" % (verdict, code))
        except Exception as exc:  # noqa: BLE001
            record("T5.6 no crash: %s" % label, False, "raised %r" % (exc,))

    # depth_rung must be a genuine int, not a string that happens to be big.
    verdict, rows = depth_gate.check(mutate(depth_rung="9"))
    r2 = [ok for r, ok, _ in rows if r == "R2 depth ladder"][0]
    record("T5.7 string rung '9' does not satisfy R2", r2 is False, "R2=%s" % r2)

    # fix_number 1.9 must not be rounded up into "second plaster" territory
    # nor smuggled past it -- it is malformed, and R1 must not silently pass.
    verdict, rows = depth_gate.check(mutate(fix_number_for_symptom=1.9))
    r1 = [ok for r, ok, _ in rows if r == "R1 plaster test"][0]
    record("T5.8 float fix_number is not silently accepted", r1 is False, "R1=%s" % r1)

    # evidence_is_about must be exactly the subject/proxy pair.
    verdict, rows = depth_gate.check(mutate(evidence_is_about="probably"))
    r3e = [ok for r, ok, _ in rows if r == "R3 escape test"][0]
    record("T5.9 'probably' is not a valid evidence target", r3e is False, "R3=%s" % r3e)

    # The permanence list must not be defeated by capitalisation.
    verdict, rows = depth_gate.check(
        mutate(claim="Fixed for GOOD", depth_rung=3))
    rp = [ok for r, ok, _ in rows if r == "R2 permanence claim"][0]
    record("T5.10 permanence claim is case-insensitive", rp is False, "R2perm=%s" % rp)

    # A rung above the ladder is an invented rung, not a good one.
    verdict, rows = depth_gate.check(mutate(depth_rung=5))
    r2 = [ok for r, ok, _ in rows if r == "R2 depth ladder"][0]
    record("T5.11 rung 5 is outside the ladder", r2 is False, "R2=%s" % r2)

    # bool must not pass as an int anywhere (bool is a subclass of int).
    for label, kw in [("rung True", {"depth_rung": True}),
                      ("fix_number True", {"fix_number_for_symptom": True})]:
        verdict, rows = depth_gate.check(mutate(**kw))
        bad = [r for r, ok, _ in rows if not ok]
        record("T5.12 bool rejected as int: %s" % label,
               bool(bad), "failed=%s" % (bad or "none"))

    # A negative or zero attempt count is not a real attempt.
    for val in (0, -1):
        verdict, rows = depth_gate.check(mutate(fix_number_for_symptom=val))
        r1 = [ok for r, ok, _ in rows if r == "R1 plaster test"][0]
        record("T5.13 fix_number=%s is not an attempt" % val, r1 is False, "R1=%s" % r1)


# ==========================================================================
# T6 -- self-consistency: the gate must not silently pass a record that
#       literally admits it is a proxy.  The record's own words are evidence.
# ==========================================================================
def t6_self_consistency():
    print("\nT6  SELF-CONSISTENCY")
    rec = mutate(
        evidence_is_about="subject",
        claim="All 9 profiles answer HTTP 200",
        evidence="9 processes bound to 9 distinct ports; card lists 9 served agents",
        subject="A2A and relay exposed per profile in the Hermes gateway",
    )
    verdict, rows = depth_gate.check(rec)
    r3 = [ok for r, ok, _ in rows if r == "R3 escape test"][0]
    record("T6.1 gate trusts the declared field, not prose",
           r3 is True and verdict in ("PASS", "FAIL"),
           "R3=%s verdict=%s (documented limitation, see below)" % (r3, verdict))

    # These were dead code: both passed a hardcoded literal True, so an audit
    # correctly called them "counted, not asserting". They are now REAL
    # assertions -- they read SKILL.md and fail if the disclosure is removed.
    # A limitation that disappears when you delete the sentence documenting it
    # is not a limitation anyone is actually held to.
    skill_md = os.path.join(HERE, os.pardir, "SKILL.md")
    try:
        with open(skill_md, encoding="utf-8") as fh:
            doc = fh.read().lower()
        have_doc = True
    except OSError:
        doc, have_doc = "", False

    record("T6.2 SKILL.md is present to disclose limitations into", have_doc,
           "SKILL.md unreadable at %s" % skill_md)
    record("T6.3 disclosed: the gate is a schema linter, not a judge",
           have_doc and "schema linter" in doc,
           "removed disclosure -- the gate would overclaim itself")
    record("T6.4 disclosed: every semantic field is a self-declaration",
           have_doc and "self-declar" in doc, "")
    record("T6.5 disclosed: restatement overlap is gameable by padding",
           have_doc and "gameable" in doc, "")
    record("T6.6 disclosed: a PASS does not mean the subject is finished",
           have_doc and "the subject is finished" in doc, "")


def t7_honest_paraphrase_passes():
    """The defect that mattered most.

    The first implementation compared a literal 24-character prefix and failed the
    reference HONEST record, because an honest restatement does not reuse the
    subject's exact word order. A gate that punishes truth teaches its author to
    flatter the gate. These are the regression guards.
    """
    print("\nT7  DOES IT PUNISH HONEST PARAPHRASE?  (regression guards)")
    cases = [
        ("reordered wording", "A gateway in which each of the 9 profiles has its own "
                             "A2A and relay, was asked for. That is now each profile "
                             "serving its own relay and A2A endpoint."),
        ("synonyms for the verb", "A2A and relay exposed per profile in the Hermes "
                                  "gateway. That is now up and live for every single "
                                  "profile in the Hermes gateway."),
        ("contracted phrasing", "Per-profile A2A and relay in the Hermes gateway was "
                                "requested. It is now delivered for all 9 profiles."),
    ]
    for label, sr in cases:
        rec = mutate(subject_restated=sr)
        verdict, rows = depth_gate.check(rec)
        r3 = [ok for r, ok, _ in rows if r == "R3 subject restatement"][0]
        record("T7.1 %s is not punished" % label, r3 is True, "R3=%s verdict=%s" % (r3, verdict))

    # And the mirror: something that is NOT the subject's wording must still fail.
    for label, sr in [
        ("generic all-clear", "Everything is working fine now."),
        ("unrelated boast", "I finished the deployment and everything is great."),
        ("bare affirmation", "Done."),
    ]:
        rec = mutate(subject_restated=sr)
        verdict, rows = depth_gate.check(rec)
        r3 = [ok for r, ok, _ in rows if r == "R3 subject restatement"][0]
        record("T7.2 %s is rejected" % label, r3 is False, "R3=%s" % r3)

    # Word order must not matter, and the threshold must sit where a genuine
    # restatement clears it while a vague one does not.
    frac = depth_gate._overlap(
        PASS_RECORD["subject"], PASS_RECORD["subject_restated"])
    record("T7.3 reference record overlap clears threshold",
           frac >= depth_gate.RESTATE_MIN_OVERLAP, "%.0f%%" % (frac * 100))
    frac_bad = depth_gate._overlap(PASS_RECORD["subject"], "Everything is working fine now.")
    record("T7.4 generic all-clear below threshold",
           frac_bad < depth_gate.RESTATE_MIN_OVERLAP, "%.0f%%" % (frac_bad * 100))


def t8_audited_adversarial():
    """Cases an INDEPENDENT verifier wrote to try to break this gate.

    Two of these were holes the audit found and the gate did not stop:
    empty/placeholder evidence, and evidence that narrates a repeat attempt while
    the record claims the first fix. Both now have rules. The rest are recorded
    as known-and-accepted so they can never be quietly forgotten.
    """
    print("\nT8  INDEPENDENTLY-AUDITED ADVERSARIAL CASES")

    # --- holes the audit found; these MUST now be caught -------------------
    rec = mutate(evidence="")
    verdict, rows = depth_gate.check(rec)
    r4 = [ok for r, ok, _ in rows if r == "R4 evidence substance"][0]
    record("T8.1 empty evidence is caught (was a hole)", r4 is False, "R4=%s" % r4)

    for ph in ("verified", "done", "tested", "fine", "works", "OK"):
        verdict, rows = depth_gate.check(mutate(evidence=ph))
        r4 = [ok for r, ok, _ in rows if r == "R4 evidence substance"][0]
        record("T8.2 placeholder evidence %r is caught" % ph, r4 is False, "R4=%s" % r4)

    rec = mutate(
        fix_number_for_symptom=1,
        evidence="applied only after a third attempt, and the config was restored "
                 "three separate times before it finally held",
    )
    verdict, rows = depth_gate.check(rec)
    r1 = [ok for r, ok, _ in rows if r == "R1 plaster test"][0]
    record("T8.3 evidence narrating a repeat attempt is caught (was a hole)",
           r1 is False, "R1=%s" % r1)

    # The marker list must NOT fire on the vocabulary a FIXED record uses. The
    # first draft used a flat list including "revert" and "restor" and failed
    # case_a2a_proxy, whose evidence honestly said "no longer reverts". A marker
    # list broad enough to catch a lazy author also catches a truthful one.
    for ph in ("no longer reverts", "the value was restored once and held",
               "the marker is cleared and does not return", "already reverted away"):
        rec = mutate(fix_number_for_symptom=1,
                     evidence=ph + " ; nine processes bound to nine distinct ports "
                                   "and the card lists nine served agents")
        r1 = [ok for r, ok, _ in depth_gate.check(rec)[1] if r == "R1 plaster test"][0]
        record("T8.3b honest %r does not trip R1" % ph[:28], r1 is True, "R1=%s" % r1)

    # A second audit then found the opposite error: the narrowed list MISSED the
    # phrasings that actually describe repetition. Each of these must now fail.
    for ph in ("the config was restored three separate times before it held",
               "the value reverted again after the second boot",
               "I had to retry the deployment before it settled",
               "the patch was rewritten multiple times",
               "the card was rewritten 2 times by the publisher",
               "several restores and it still came back",
               "the file was rewritten twice before it held",
               "retried three times with the same error"):
        rec = mutate(fix_number_for_symptom=1, evidence=ph)
        r1 = [ok for r, ok, _ in depth_gate.check(rec)[1] if r == "R1 plaster test"][0]
        record("T8.3c repetition caught: %r" % ph[:34], r1 is False, "R1=%s" % r1)

    # Stems must cover their inflections. "rewritten" does not contain
    # "rewrite"; "rebuilt" does not contain "rebuild"; "retries" does not
    # contain "retry". A prior list missed all three in their common forms.
    for ph in ("the card was rewritten 2 times by the publisher",
               "the service was rebuilt twice overnight",
               "retried three times with the same error",
               "the model was reinstated three times by the healer",
               "the file was repaired twice before it held"):
        rec = mutate(fix_number_for_symptom=1, evidence=ph)
        r1 = [ok for r, ok, _ in depth_gate.check(rec)[1] if r == "R1 plaster test"][0]
        record("T8.3h inflection caught: %r" % ph[:34], r1 is False, "R1=%s" % r1)

    # The fourth audit found the count rule convicting MEASUREMENT prose --    # "the suite passed 3 times in a row", "3x faster", "the port was probed
    # twice by healthcheck". Those describe what was observed, not how many
    # times I patched something. A count alone no longer trips R1; it must be
    # paired with a repair action.
    for ph in ("the suite passed 3 times in a row, 0 flakes",
               "3x faster render than the previous build",
               "2x speedup confirmed on the second machine",
               "the port was probed twice by healthcheck and once by me",
               "2 attempts are needed when the cache is cold; one on warm boot",
               "3 attempts are documented in the runbook as expected",
               "the config file was read 3 times by the loader",
               "verified 3 times across 2 boots",
               "the writer was traced, and it overwrites the file 3 times per boot",
               "I re-read the writer three times to find the second one",
               "second pass over the config, no rewrite needed"):
        rec = mutate(fix_number_for_symptom=1, evidence=ph)
        r1 = [ok for r, ok, _ in depth_gate.check(rec)[1] if r == "R1 plaster test"][0]
        record("T8.3f measurement prose NOT convicted: %r" % ph[:34], r1 is True,
               "R1=%s" % r1)

    # Guard the E5 fix directly. Re-adding "overwrit" to REPEAT_ACTIONS is
    # exactly what an audit mutation did, and it was NOT caught by the
    # behavioural fixtures, because the guard phrase used the past tense
    # ("overwrote") which "overwrit" does not match. Assert the list contents.
    record("T8.3g 'overwrit' absent from REPEAT_ACTIONS",
           "overwrit" not in depth_gate.REPEAT_ACTIONS, "list contents guarded")
    record("T8.3g 'overwrit' absent from REPEAT_QUALIFIERS",
           "overwrit" not in depth_gate.REPEAT_QUALIFIERS, "list contents guarded")

    # A fifth audit found the actions were raw SUBSTRINGS, producing ten false
    # positives: "retr" matched RETRIEVED, "patch" matched DISPATCHED, "fix"
    # matched FIXTURE and PREFIX, "times" matched SOMETIMES. Every one of these
    # is honest prose and must stay unconvicted.
    for ph in ("the profile was retrieved three times from the vault",
               "the webhook was dispatched twice because the upstream timed out",
               "the fixture passed twice before the change",
               "the prefix was left alone; verified twice",
               "the suffix of the key was redacted once, verified twice",
               "I patched the scheduler; it sometimes drifts",
               "the retrieval layer cached the value twice",
               "the dispatch queue drained twice in an hour",
               "profit was up, and the config was patched once"):
        rec = mutate(fix_number_for_symptom=1, evidence=ph)
        r1 = [ok for r, ok, _ in depth_gate.check(rec)[1] if r == "R1 plaster test"][0]
        record("T8.3j substring false positive NOT convicted: %r" % ph[:34], r1 is True,
               "R1=%s" % r1)

    # A repetition word in one clause must not combine with a repair verb in
    # another. Both halves are honest on their own.
    for ph in ("the second run was clean and the config was patched",
               "several profiles answered; the card was rebuilt once",
               "another boot happened, and the value was restored"):
        rec = mutate(fix_number_for_symptom=1, evidence=ph)
        r1 = [ok for r, ok, _ in depth_gate.check(rec)[1] if r == "R1 plaster test"][0]
        record("T8.3k cross-clause leak NOT convicted: %r" % ph[:34], r1 is True,
               "R1=%s" % r1)

    # The irregulars added last round were unguarded -- a mutation deleting
    # "redo"/"redone"/"redid" survived the suite. And "rewrote" was claimed in
    # SKILL.md as "listed outright" while it was never in the list at all.
    for ph in ("I rewrote the config three times before it held",
               "the value was redone twice by the healer",
               "I redid the whole repair and it reverted again",
               "rewrote the launcher registration three times"):
        rec = mutate(fix_number_for_symptom=1, evidence=ph)
        r1 = [ok for r, ok, _ in depth_gate.check(rec)[1] if r == "R1 plaster test"][0]
        record("T8.3l irregular caught: %r" % ph[:34], r1 is False, "R1=%s" % r1)

    # KNOWN BLIND SPOTS, not failures. A bare "again" after an ordinary verb is
    # genuinely ambiguous -- "ran it again" and "flipped the flag again" read as
    # repeated repair, but "verified again, same result" does not, and nothing in
    # the string distinguishes them without parsing the sentence. Widening the
    # heuristic to catch the first two was tried and rejected: it convicted
    # honest re-verification. These pass, and that is the accepted cost.
    for ph in ("ran it again the next morning",
               "flipped the flag again and it still failed",
               "two attempts were needed before it held",
               "restarted the service twice without effect",
               "I edited the config three times before it held"):
        rec = mutate(fix_number_for_symptom=1, evidence=ph)
        r1 = [ok for r, ok, _ in depth_gate.check(rec)[1] if r == "R1 plaster test"][0]
        record("T8.3e KNOWN BLIND SPOT: %r" % ph[:32], r1 is True,
               "R1=%s -- accepted limitation" % r1)

    # KNOWN FALSE POSITIVE, disclosed. A NOUN "retry" describing system behaviour
    # trips the rule even though nobody was fixing anything. Distinguishing the
    # verb "I retried" from the noun "a retry upstream" needs parsing the
    # sentence, and every attempt to key on that misfired on honest prose. Recorded
    # rather than hidden.
    for ph in ("the webhook was dispatched twice because of a retry upstream",):
        rec = mutate(fix_number_for_symptom=1, evidence=ph)
        r1 = [ok for r, ok, _ in depth_gate.check(rec)[1] if r == "R1 plaster test"][0]
        record("T8.3m KNOWN FALSE POSITIVE: %r" % ph[:34], r1 is False,
               "R1=%s -- noun form, disclosed" % r1)

    # A count noun without a repair verb is not a plaster: "one attempt" is
    # singular, and "attempt" is not a repair verb the rule tracks.
    for ph in ("one attempt is documented in the runbook for a cold cache",
               "the runbook describes 3 attempts as expected behaviour"):
        rec = mutate(fix_number_for_symptom=1, evidence=ph)
        r1 = [ok for r, ok, _ in depth_gate.check(rec)[1] if r == "R1 plaster test"][0]
        record("T8.3n count noun alone NOT convicted: %r" % ph[:34], r1 is True,
               "R1=%s" % r1)

    # A repair action under a negation describes a repair that did NOT happen,
    # so it cannot contradict a claim about repairs that did.
    for ph in ("second pass over the config, no rewrite needed",
               "the config was never restored to the broken value",
               "no patch was required; the healer self-cleared the marker",
               "without any manual fix the marker cleared itself"):
        rec = mutate(fix_number_for_symptom=1, evidence=ph)
        r1 = [ok for r, ok, _ in depth_gate.check(rec)[1] if r == "R1 plaster test"][0]
        record("T8.3i negated action NOT convicted: %r" % ph[:34], r1 is True,
               "R1=%s" % r1)

    # The third audit found the OPPOSITE error again: the standalone list was
    # convicting exactly the behaviour this skill exists to produce. Reading the
    # file that overwrites the config is the anti-plaster move, not a plaster.
    for ph in ("I had to read the file to find the writer that overwrote it",
               "verified once more, no change since",
               "checked it one more time and the value held",
               "I tried again on a clean checkout and it behaved",
               "the writer was found by tracing boot order, not by retrying"):
        rec = mutate(fix_number_for_symptom=1, evidence=ph)
        r1 = [ok for r, ok, _ in depth_gate.check(rec)[1] if r == "R1 plaster test"][0]
        record("T8.3d NOT a plaster: %r" % ph[:34], r1 is True, "R1=%s" % r1)

    # Every one of the three real records must still survive the new rules --
    # a new rule that breaks honest evidence is the exact defect this suite
    # exists to prevent, so each real record is re-checked here.
    base = "C:\\Users\\apviz\\.learn\\subject-completion"
    EXPECTED_FAILS = {
        # The A2A record must fail ONLY on the proxy declaration. It originally also
        # failed R1, because its evidence says "no longer reverts" and "revert" was
        # in the marker list -- a false positive on an honest record.
        "case_a2a_proxy": {"R3 escape test"},
        "case_ingest_proxy": {"R2 depth ladder", "R3 escape test"},
        "case_config_plaster": {"R1 plaster test", "R2 depth ladder", "R2 permanence claim"},
    }
    # Previously these blocks were skipped when the directory was absent, so
    # deleting the fixtures silently dropped the assertions and the suite still
    # exited 0. Missing fixtures are now a FAILURE, not a skip.
    if not os.path.isdir(base):
        record("T8.4 the real record fixtures exist", False,
               "MISSING: %s -- these assertions cannot be skipped" % base)
    else:
        for name, expected in EXPECTED_FAILS.items():
            path = os.path.join(base, name + ".json")
            if not os.path.isfile(path):
                record("T8.4 %s fixture exists" % name, False, "MISSING: %s" % path)
                continue
            with open(path, encoding="utf-8") as fh:
                rec = json.load(fh)
            verdict, rows = depth_gate.check(rec)
            got = {r for r, ok, _ in rows if not ok}
            record("T8.4 %s fails exactly the expected rules" % name,
                   verdict == "FAIL" and got == expected,
                   "got=%s" % (sorted(got) or "none"))
            e_ok = [ok for r, ok, _ in rows if r == "R4 evidence substance"][0]
            record("T8.4 %s still has substantive evidence" % name, e_ok is True, "R4=%s" % e_ok)

    # --- cases the gate genuinely does NOT stop; recorded, not hidden ------
    # A1: a proxy mislabelled as the subject. The declared field is trusted.
    rec = mutate(evidence_is_about="subject",
                 claim="Hermes is healthy",
                 evidence="nine local HTTP endpoints each returned status 200 within "
                          "eleven milliseconds of the request being issued")
    verdict, _ = depth_gate.check(rec)
    record("T8.5 KNOWN: mislabelled proxy passes (declared field trusted)",
           verdict == "PASS", "verdict=%s -- accepted limitation" % verdict)

    # A2: padding the restatement with the subject's own words.
    padded = " ".join(["A2A relay profile gateway"] * 12)
    rec = mutate(subject_restated=padded)
    r3 = [ok for r, ok, _ in depth_gate.check(rec)[1]
          if r == "R3 subject restatement"][0]
    record("T8.6 KNOWN: keyword-padded restatement passes (token overlap gameable)",
           r3 is True, "R3=%s -- accepted limitation" % r3)

    # A4: declaring a rung the work never reached.
    rec = mutate(depth_rung=4)
    verdict, _ = depth_gate.check(rec)
    record("T8.7 KNOWN: an inflated depth_rung passes (self-declared)",
           verdict == "PASS", "verdict=%s -- accepted limitation" % verdict)

    # The second audit found the new evidence-substance rule REJECTED canonical
    # honest evidence, because _significant() drops every token under 4 chars and
    # therefore every digit. In this domain a number often IS the measurement.
    print("\nT8b  CANONICAL EVIDENCE MUST NOT BE REJECTED AS TOO THIN")
    for ph in ("HTTP 200 on 9/9 endpoints",
               "M3 returned 200 on all 9 profiles within 11ms",
               "9/9 profiles bound to distinct ports 8642, 8644, 9900",
               "43 top-level keys, 34 mcp_servers, _config_version 49",
               "v0.21.5+5697 pending marker cleared on next boot",
               "九个配置档位全部正确响应，端口均已绑定",
               "port 9900 lists 9 served agents, 0 missing",
               "ช่องทั้งเก้าตอบสนองถูกต้องและผูกพอร์ตแล้ว",
               "配置已修復並保持穩定，連接埠全部綁定成功"):
        rec = mutate(evidence=ph)
        verdict, rows = depth_gate.check(rec)
        e_ok = [ok for r, ok, _ in rows if r == "R4 evidence substance"][0]
        record("T8b.1 accepted: %r" % ph[:40], e_ok is True, "R4=%s" % e_ok)

    # DELIBERATE rejections. The floor is 3 substantive tokens. A terse status
    # line is an assertion, not a measurement -- and "0 errors in the log" is
    # this skill's own named anti-pattern, so it MUST be rejected.
    for ph in ("", "verified", "done", "OK", "tested", "fine", "works",
               "n/a", "true", "pass", "0 errors", "all good", "no errors"):
        rec = mutate(evidence=ph)
        verdict, rows = depth_gate.check(rec)
        e_ok = [ok for r, ok, _ in rows if r == "R4 evidence substance"][0]
        record("T8b.2 deliberately rejected: %r" % ph, e_ok is False, "R4=%s" % e_ok)

    # A number must count ONCE. A third audit found "8642" was scored twice
    # (once as a 4-char word, once as a numeral), so three bare numbers scored
    # six tokens and cleared a floor that a real sentence could not.
    one = depth_gate._evidence_tokens("8642")
    three = depth_gate._evidence_tokens("8642 8644 9900")
    record("T8b.3 a single number scores 1, not 2", len(one) == 1, "n=%d" % len(one))
    record("T8b.4 three numbers score 3, not 6", len(three) == 3, "n=%d" % len(three))
    wordy = depth_gate._evidence_tokens("alpha bravo charlie")
    record("T8b.5 three numbers are scored the same way as three words",
           len(three) == len(wordy) == 3,
           "numbers=%d words=%d" % (len(three), len(wordy)))

    # Known and accepted: evidence below the floor is rejected even when the
    # numbers in it are real. "200 on 9/9" is terse but true; the gate demands
    # the record be written out. Recorded so the limit is visible, not hidden.
    rec = mutate(evidence="200 on 9/9")
    e_ok = [ok for r, ok, _ in depth_gate.check(rec)[1]
            if r == "R4 evidence substance"][0]
    record("T8b.6 KNOWN: terse true evidence is rejected (floor is 3)",
           e_ok is False, "R4=%s -- deliberate floor, disclosed" % e_ok)



def t9_evidence_tokens_edge_cases():
    print("\nT9  EVIDENCE TOKENS EDGE CASES")

    cases = [
        ("T9.1 None yields empty", None, set()),
        ("T9.2 empty string yields empty", "", set()),
        ("T9.3 stopwords only yields empty", "the and for that this with", set()),
        ("T9.4 placeholders only yields empty", "verified tested works fine done", set()),
        ("T9.5 numerals get prefix", "123 456", {"\x00123", "\x00456"}),
        ("T9.6 alphanumeric numerals get prefix", "v0.21.5 9/9 M3", {"\x00v0.21.5", "\x009/9", "\x00m3"}),
        ("T9.7 plain english words length >= 4", "endpoints network connection", {"endpoints", "network", "connection"}),
        ("T9.8 short plain words are excluded", "net con", set()),
        ("T9.9 punctuation is stripped", "hello, world! (test) [done]", {"hello", "world", "test"}),
        ("T9.10 CJK grouped by 4 chars", "测试测试", {"\x00u0", "测试测试"}),
        ("T9.11 CJK grouped by 4 chars (8 chars)", "测试测试测试测试", {"\x00u0", "\x00u1", "测试测试测试测试"}),
        ("T9.12 whitespace strings yield empty", "  \n\t  ", set()),
        ("T9.13 punctuation only yield empty", "!!! ...", set()),
    ]

    for name, input_val, expected in cases:
        actual = depth_gate._evidence_tokens(input_val)
        record(name, actual == expected, "expected %r, got %r" % (expected, actual))


def main():
    print("=" * 78)
    print("test_depth_gate.py -- does the gate discriminate?")
    print("=" * 78)
    for fn in (t1_can_pass, t2_each_rule_catches, t3_sensitive,
               t9_evidence_tokens_edge_cases,
               t4_reports_every_failure, t5_shape_abuse, t6_self_consistency,
               t7_honest_paraphrase_passes, t8_audited_adversarial):
        fn()

    passed = sum(1 for _, ok, _ in RESULTS if ok)
    failed = [(n, d) for n, ok, d in RESULTS if not ok]
    print("\n" + "=" * 78)
    print("%d/%d assertions passed" % (passed, len(RESULTS)))
    if failed:
        print("\nDEFECTS IN THE GATE (or in this suite's expectations):")
        for n, d in failed:
            print("  - %s  %s" % (n, d))
        print("=" * 78)
        return 1
    print("VERDICT: the gate discriminates. It can pass, and it catches each rule.")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
