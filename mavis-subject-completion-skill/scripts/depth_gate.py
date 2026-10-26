"""depth_gate.py -- the runnable form of the subject-completion rules.

Reads a closure record (JSON) and returns a verdict. It exists because prose rules
do not stop anything: the plaster test, the depth rung, and the proxy check have to
be mechanically enforced at the moment "done" is about to be claimed.

    python depth_gate.py record.json
    exit 0 = PASS   1 = FAIL   2 = INCOMPLETE (record missing required fields)

Record schema (all fields required unless marked optional):

    {
      "subject":             "the operator's ask, in their words",
      "subject_restated":    "The operator asked for ___. That is now ___.",
      "claim":               "what I assert is true now",
      "evidence":            "what I actually measured",
      "evidence_is_about":   "subject" | "proxy",
      "fix_number_for_symptom": 1,          # 2+ means the diagnosis is unfinished
      "depth_rung":          3,             # 1 symptom .. 4 will-not-recur
      "independent_evidence": true,         # measured by something I did not build
      "instrument_built_by_me": false
    }
"""
from __future__ import annotations

import json
import re
import sys

REQUIRED = [
    "subject", "subject_restated", "claim", "evidence", "evidence_is_about",
    "fix_number_for_symptom", "depth_rung", "independent_evidence",
    "instrument_built_by_me",
]

# Words that assert permanence. Claiming rung 4 behaviour at a lower rung is the
# overclaim this gate exists to catch. Matched case-insensitively.
PERMANENCE = ("will not recur", "will never", "permanently", "for good", "fully solved",
              "done for good", "no longer possible")

# Fraction of the subject's significant words that must reappear in the
# restatement. A prefix match was tried and rejected: it failed honest
# paraphrases ("exposed per profile" vs "per profile"), which trains the author to
# flatter the gate instead of writing the truth. Token overlap survives reordering
# and minor wording while still rejecting "everything is working fine now".
RESTATE_MIN_OVERLAP = 0.6

# Words too short or too generic to carry meaning.
_STOP = frozenset((
    "the", "and", "for", "that", "this", "with", "from", "into", "have", "has",
    "was", "were", "are", "but", "not", "you", "your", "its", "it's", "their",
    "them", "then", "than", "when", "what", "which", "will", "would", "can",
    "could", "should", "been", "being", "here", "there", "them", "they",
    "themself", "myself", "yourself", "ours", "ourselves", "us", "our", "now",
))


# Tokens that satisfy the length filter but carry no measurement. An `evidence`
# field containing only these is an assertion, not a measurement.
_PLACEHOLDER_EVIDENCE = frozenset((
    "verified", "done", "tested", "checked", "complete", "completed", "working",
    "works", "fine", "good", "passed", "passing", "success", "successful", "okay",
    "valid", "correct", "present", "exists", "resolved", "fixed", "applied",
    "nope", "null", "bool", "int", "str", "list", "dict", "json", "none",
))

# Minimum distinct non-placeholder tokens for `evidence` to count as a measurement.
EVIDENCE_MIN_TOKENS = 3

# Words that mark a REPEATED action, and words that mark REPETITION. A contradiction
# requires BOTH: an action word and a repetition word. Checking either alone punishes
# honest records -- "no longer reverts" and "restored once and held" are what a FIXED
# closure says, and both contain an action word with no repetition. The first draft of
# this rule used a flat list including "revert" and "restor", and an independent audit
# caught it failing a truthful real record because of exactly that.
# Repair actions, as WORD-BOUNDED patterns.
#
# These were plain substrings, and an audit found ten false positives caused by
# that alone: "retr" matched RETRIEVED, "patch" matched DISPATCHED, "fix" matched
# FIXTURE and PREFIX, "times" matched SOMETIMES. Each pattern below is anchored on
# a word boundary and lists the inflections it accepts, so it matches the verb it
# means and nothing else. "retry" no longer matches "retrieved"; "fix" no longer
# matches "fixture"; "rewrote" is covered, which the previous list did NOT do
# despite SKILL.md claiming it did.
REPEAT_ACTIONS = (
    r"\brestor(?:e|es|ed|ing)\b",
    r"\brevert(?:s|ed|ing)\b",
    r"\bretr(?:y|ies|ied|ying)\b",
    r"\bre-?appl(?:y|ies|ied|ying)\b",
    r"\bfix(?:es|ed|ing)?\b",
    r"\bpatch(?:es|ed|ing)?\b",
    r"\brewrit(?:e|es|ing|ten)\b|\brewrote\b",
    r"\bcorrections?\b",
    r"\breinstall(?:ed|s|ing)?\b|\breinstat(?:ed|ing)\b",
    r"\brepairs?(?:ed|ing)?\b",
    r"\bredone?\b|\bredid\b",
    r"\brebuilt\b|\brebuild(?:s|ing)?\b",
    r"\bredeploy(?:ed|s|ing|ment)?\b",
)
_REPEAT_ACTIONS_RE = tuple(re.compile(p) for p in REPEAT_ACTIONS)

# Repetition words, also word-bounded. "sometimes" must not read as "times".
REPEAT_QUALIFIERS = (
    r"\bagain\b", r"\btwice\b", r"\btimes\b", r"\brepeatedly\b", r"\bkeeps?\b",
    r"\bkept\b", r"\bmultiple\b", r"\bseveral\b", r"\banother\b", r"\bsecond\b",
    r"\bthird\b", r"\bmore than once\b", r"\bhad to\b",
)
_REPEAT_QUALIFIERS_RE = tuple(re.compile(p) for p in REPEAT_QUALIFIERS)

# A repair action under a negation describes something that did NOT happen.
# "second pass over the config, no rewrite needed" is honest prose, and an audit
# showed the gate convicting it. Looked for both before and after the verb: the
# negator is not always on the left ("the rewrite was not needed").
NEGATORS = (r"\bno\b", r"\bnot\b", r"\bnever\b", r"\bwithout\b", r"\bzero\b",
            r"\bneither\b", r"\bnothing\b")
_NEGATORS_RE = tuple(re.compile(p) for p in NEGATORS)

# Clauses are split before matching, so a repetition word in one clause cannot
# combine with a repair verb in another. "the second run was clean and the config
# was patched" is one honest fix, not a repeated one.
CLAUSE_SPLIT_RE = re.compile(r"[,;.!?]+|\s+and\s+|\s+but\s+|\s+then\s+")
REPEAT_QUALIFIERS = (
    "again", "twice", "times", "repeatedly", "keeps", "kept", "multiple",
    "several", "another", "second", "third", "more than once", "had to",
)
# Repetition phrases strong enough to stand alone.
#
# This list was deliberately cut down. An earlier version included "had to",
# "once more" and "one more time", and an audit showed they fire on exactly the
# behaviour this skill exists to produce -- "I had to read the file to find the
# writer that overwrote it" and "verified once more, no change since" are
# CORRECT closure prose, and the gate was convicting them as plasters. Every
# entry below is unambiguously a repeat attempt at the work.
REPEAT_STANDALONE = (
    "for the second time", "for the third time", "yet again",
    "another attempt", "second attempt", "third attempt",
)
# Explicit counts, e.g. "two attempts", "3 times", "edited three times", "twice".
#
# This alone is NOT sufficient to fail a record. An audit showed that a bare count
# rule convicts ordinary MEASUREMENT prose -- "the suite passed 3 times in a row",
# "the port was probed twice by healthcheck", "3x faster", "2 attempts are needed
# when the cache is cold". Those are honest descriptions of what was observed, and
# the gate exists to catch plaster, not to distrust numbers. A count therefore only
# contradicts a "first fix" claim when a repair action is present as well.
#
# "\d+x" was deliberately removed: "3x faster" and "2x speedup" are multipliers
# describing performance, never repetition of a fix.
REPEAT_COUNT_RE = re.compile(
    r"\b(?:2|3|4|5|two|three|four|five|six|several|multiple|many)\s+"
    r"(?:attempts?|tries|times|fixes|fix|restores|restored|passes|reruns|re-runs)\b"
    r"|\b(?:twice|thrice)\b"
)
# Kept for backwards compatibility with callers that imported the old name.
ATTEMPT_MARKERS = REPEAT_ACTIONS


def _negated(clause, pattern):
    """True when every match of `pattern` in `clause` sits under a negation.

    Checks a window on BOTH sides: the negator is not always on the left
    ("no rewrite needed" but also "the rewrite was not needed").
    """
    hits = list(pattern.finditer(clause))
    if not hits:
        return False
    for m in hits:
        left = clause[max(0, m.start() - 30):m.start()]
        right = clause[m.end():m.end() + 18]
        if not (any(n.search(left) for n in _NEGATORS_RE)
                or any(n.search(right) for n in _NEGATORS_RE)):
            return False
    return True


def _repeat_contradiction(evidence):
    """Return a description of what makes a 'first fix' claim untrue.

    Matched clause by clause, so a repetition word and a repair verb must occur
    in the same clause to combine. Fires on a standalone repetition phrase in a
    clause, or on a repair action together with a repetition word or a count
    pattern in that same clause. Returns None otherwise.
    """
    low = str(evidence).lower()
    for phrase in REPEAT_STANDALONE:
        if phrase in low:
            return "standalone repetition phrase %r" % phrase
    for clause in CLAUSE_SPLIT_RE.split(low):
        if not clause:
            continue
        acts = [a.pattern for a in _REPEAT_ACTIONS_RE
                if a.search(clause) and not _negated(clause, a)]
        if not acts:
            continue
        m = REPEAT_COUNT_RE.search(clause)
        if m:
            return "%s + count pattern %r" % (acts[0], m.group(0))
        quals = [q.pattern for q in _REPEAT_QUALIFIERS_RE if q.search(clause)]
        if quals:
            return "%s + %s" % (acts[0], quals[0])
    return None


def _significant(text):
    """Distinctive lowercase word tokens, length >= 4, stopwords removed."""
    out = set()
    for raw in str(text).split():
        tok = raw.strip(".,;:!?\"'()[]{}`").lower()
        if len(tok) >= 4 and tok not in _STOP:
            out.add(tok)
    return out


def _evidence_tokens(evidence):
    """Distinctive tokens in `evidence` with placeholder words removed.

    Numbers count. A measurement in this domain is very often a number -- "HTTP 200",
    "9/9 endpoints", "43 keys", "M3". The first draft of this rule used _significant()
    alone, which silently dropped every token under 4 characters and therefore every
    digit, so honest short evidence like "HTTP 200 on 9/9 endpoints" was rejected as
    too thin. An independent audit caught that.

    Scripts without whitespace (CJK and similar) are counted in groups of 4
    characters, so a non-English measurement is not rejected merely for lacking
    spaces.
    """
    text = str(evidence)
    toks = set()

    # Numerals and alphanumeric tokens: "200", "9/9", "M3", "v0.21.5", "8642".
    # Counted here and ONLY here. An earlier version added these on top of
    # _significant(), which had already accepted any digit-bearing token of 4+
    # characters -- so "8642" scored twice and three numbers scored six, letting
    # thin numeric evidence clear the floor that a full sentence could not.
    for raw in text.split():
        tok = raw.strip(".,;:!?\"'()[]{}`").lower()
        if tok and any(ch.isdigit() for ch in tok):
            toks.add("\x00" + tok)      # \x00 namespace: never collides with a word

    # Words of 4+ characters that carry no digits.
    for raw in text.split():
        tok = raw.strip(".,;:!?\"'()[]{}`").lower()
        if len(tok) >= 4 and tok not in _STOP and not any(ch.isdigit() for ch in tok):
            toks.add(tok)

    # Unspaced scripts: 4 characters per unit of substance. Covers CJK and the
    # other space-less writing systems -- Thai, Khmer and Devanagari would all
    # otherwise score zero tokens and be rejected for having no whitespace.
    spaced_scripts = 0
    for ch in text:
        o = ord(ch)
        if (0x4E00 <= o <= 0x9FFF        # CJK
                or 0x3040 <= o <= 0x30FF   # kana
                or 0xAC00 <= o <= 0xD7AF   # hangul
                or 0x0E00 <= o <= 0x0E7F   # thai
                or 0x1780 <= o <= 0x17FF   # khmer
                or 0x0900 <= o <= 0x097F):  # devanagari
            spaced_scripts += 1
    for i in range(spaced_scripts // 4):
        toks.add("\x00u%d" % i)

    return toks - _PLACEHOLDER_EVIDENCE


def _overlap(subject, restated):
    """Fraction of the subject's significant tokens present in the restatement."""
    subj_toks = _significant(subject)
    if not subj_toks:
        # A subject with no distinctive words cannot be verified as restated.
        return 0.0
    rest_toks = _significant(restated)
    return len(subj_toks & rest_toks) / len(subj_toks)


def _is_int(value):
    """True only for a genuine int. Rejects bool (a subclass of int) and floats."""
    return type(value) is int


def check(rec):
    """Return (verdict, [(rule, passed, reason), ...])."""
    out = []

    n = rec.get("fix_number_for_symptom")
    contradiction = _repeat_contradiction(rec.get("evidence"))
    if not _is_int(n):
        r1_ok, r1_why = False, ("fix_number_for_symptom=%r is not an int; a malformed count "
                                "may not be read as 'first fix'" % (n,))
    elif n < 1:
        r1_ok, r1_why = False, "fix_number_for_symptom=%d is not a real attempt" % n
    elif n >= 2:
        r1_ok, r1_why = False, ("fix #%d on the same symptom: a second plaster is an "
                                "unfinished diagnosis" % n)
    elif contradiction:
        r1_ok, r1_why = False, ("the evidence describes a repeated attempt (%s) while "
                                "fix_number_for_symptom=%d; one of the two is untrue"
                                % (contradiction, n))
    else:
        r1_ok, r1_why = True, "first fix at this symptom"
    out.append(("R1 plaster test", r1_ok, r1_why))

    rung = rec.get("depth_rung")
    if not _is_int(rung):
        r2_ok, r2_why = False, ("depth_rung=%r is not an int; a rung must be a real "
                                "number 1-4" % (rung,))
    elif not (1 <= rung <= 4):
        r2_ok, r2_why = False, "depth_rung=%d is outside the ladder 1-4" % rung
    elif rung >= 3:
        r2_ok, r2_why = True, "rung %d addresses the loop" % rung
    else:
        r2_ok, r2_why = False, ("rung %d: rung 1-2 is a diagnosis, not a fix; rung 3 "
                                "addresses the loop" % rung)
    out.append(("R2 depth ladder", r2_ok, r2_why))

    about = str(rec.get("evidence_is_about", "")).lower()
    out.append((
        "R3 escape test",
        about == "subject",
        "evidence proves a PROXY, not the subject '%s'" % rec.get("subject")
        if about != "subject" else
        "evidence is about the subject",
    ))

    ind = rec.get("independent_evidence")
    out.append((
        "R4 independent evidence",
        ind is True,
        "self-measurement is not verification" if ind is not True
        else "evidence from an independent instrument",
    ))

    mine = rec.get("instrument_built_by_me")
    out.append((
        "R4 instrument independence",
        mine is False,
        "the measuring instrument was built for this claim" if mine is not False
        else "instrument not self-built",
    ))

    # Added after independent audit: `evidence` was required by the schema and
    # printed by the CLI, but no rule ever inspected it -- the one field that
    # means "what I actually measured" had zero enforcement, so evidence=""
    # passed every check. It is now a rule.
    ev_toks = _evidence_tokens(rec.get("evidence"))
    ev_ok = len(ev_toks) >= EVIDENCE_MIN_TOKENS
    out.append((
        "R4 evidence substance",
        ev_ok,
        "evidence has %d substantive token(s), needs %d; empty or placeholder-only "
        "evidence is an assertion, not a measurement" % (len(ev_toks), EVIDENCE_MIN_TOKENS)
        if not ev_ok else
        "evidence carries %d substantive tokens" % len(ev_toks),
    ))

    claim = str(rec.get("claim", "")).lower()
    overclaims = [p for p in PERMANENCE if p in claim]
    rung_ok = _is_int(rung) and rung >= 4
    out.append((
        "R2 permanence claim",
        not overclaims or rung_ok,
        "claim asserts permanence but depth_rung=%r (needs 4)" % (rung,)
        if overclaims and not rung_ok else
        "no permanence overclaim",
    ))

    sr = str(rec.get("subject_restated", "")).strip()
    subj = str(rec.get("subject", "")).strip()
    frac = _overlap(subj, sr)
    restates = bool(sr) and frac >= RESTATE_MIN_OVERLAP
    out.append((
        "R3 subject restatement",
        restates,
        "subject_restated does not carry the operator's wording (%.0f%% of the subject's "
        "significant words present, needs %d%%)" % (frac * 100, RESTATE_MIN_OVERLAP * 100)
        if not restates else
        "subject restated in the operator's words (%.0f%% overlap)" % (frac * 100),
    ))

    failed = [r for r, ok, _ in out if not ok]
    return ("FAIL" if failed else "PASS"), out


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    with open(argv[1], encoding="utf-8") as fh:
        rec = json.load(fh)
    missing = [k for k in REQUIRED if k not in rec]
    if missing:
        print("INCOMPLETE - record is missing: %s" % ", ".join(missing))
        return 2

    verdict, rows = check(rec)
    print("=" * 72)
    print("SUBJECT : %s" % rec["subject"])
    print("CLAIM   : %s" % rec["claim"])
    print("EVIDENCE: %s" % rec["evidence"])
    print("=" * 72)
    for rule, ok, reason in rows:
        print("  %s  %-28s %s" % ("PASS" if ok else "FAIL", rule, reason))
    print("=" * 72)
    print("VERDICT: %s" % verdict)
    if verdict == "FAIL":
        print("A fail is not a formality. Finish the subject or say plainly it is unfinished.")
    return {"PASS": 0, "FAIL": 1}[verdict]



def _simple_evidence_tokens(evidence):
    # Removes punctuation, splits, filters to > 3 chars
    if evidence is None:
        evidence = ""
    text = re.sub(r'[^\w\s]', ' ', evidence.lower())
    return [w for w in text.split() if len(w) > 3 or w.isdigit()]

if __name__ == "__main__":
    sys.exit(main(sys.argv))
