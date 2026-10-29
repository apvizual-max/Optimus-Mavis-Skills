#!/usr/bin/env node
/**
 * verify-bg-verdict.mjs - prove the bg-verdict instrument works, and prove that
 * it can go red.
 *
 * A check that cannot fail is not a check. This verifier therefore does not
 * only prove that the instrument reports PASS on a good run: it drives
 * negative controls through the instrument and requires the wrapper to exit 1
 * and to NAME the failure (MISSING= / UNEXPECTED= / EXIT_MISMATCH).
 *
 * It also proves the inversion, which is the whole point of the instrument:
 * a command that exits 2 (a deliberately failing one) whose expected marker
 * IS present must yield wrapper exit 0, because the measurement succeeded.
 *
 * Every probe runs against FIXTURES in a temp directory. No real project, no
 * real member's runs.md, nothing outside the temp folder is written.
 *
 * Exit: 0 = every check passed, 1 = a check failed (the reason is printed).
 */

import { existsSync, readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { tmpdir } from 'node:os';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const INSTRUMENT = join(HERE, 'bg-verdict.mjs');
const FIXTURES = join(tmpdir(), 'bg-verdict-fixtures');
const LOGS = join(FIXTURES, 'logs');

const defects = [];
let checks = 0;
let warnings = 0;
let falsified = 0;

function check(id, ok, detail) {
  checks += 1;
  console.log((ok ? 'OK  ' : 'FAIL') + ' ' + id + ' ' + detail);
  if (!ok) defects.push(id + ': ' + detail);
  return ok;
}

function note(text) {
  warnings += 1;
  console.log('WARN ' + text);
}

function writeFixture(name, body) {
  const p = join(FIXTURES, name);
  writeFileSync(p, body, 'utf8');
  return p;
}

function runInstrument(extraArgs) {
  const res = spawnSync(process.execPath, [INSTRUMENT].concat(extraArgs), {
    encoding: 'utf8',
    windowsHide: true,
  });
  const out = (res.stdout || '') + (res.stderr || '');
  return { code: typeof res.status === 'number' ? res.status : -1, out: out };
}

function summaryLine(out) {
  const m = out.match(/^EXIT=.*VERDICT=(PASS|FAIL)$/m);
  return m ? m[0] : '';
}

// ---------------------------------------------------------------- fixtures --
mkdirSync(FIXTURES, { recursive: true });
mkdirSync(LOGS, { recursive: true });

const FAIL2 = writeFixture(
  'probe-exit2.mjs',
  "process.stdout.write('PROBE_RESULT=COMPLETE\\n');\n" +
    "process.stdout.write('MARKER_ALPHA\\n');\n" +
    'process.exit(2);\n'
);
const OK0 = writeFixture(
  'probe-exit0.mjs',
  "process.stdout.write('PROBE_RESULT=COMPLETE\\n');\n" +
    "process.stdout.write('MARKER_BETA\\n');\n" +
    'process.exit(0);\n'
);
const NOISE = writeFixture(
  'probe-noise.mjs',
  "process.stdout.write('MARKER_ALPHA\\n');\n" +
    "process.stderr.write('NOISE_ON_STDERR\\n');\n" +
    'process.exit(0);\n'
);

// ------------------------------------------------------------------- V1 -----
if (!check('V1.instrument-exists', existsSync(INSTRUMENT), INSTRUMENT)) {
  console.log('SUMMARY checks=' + checks + ' failed=' + defects.length + ' warnings=' + warnings + ' falsified=' + falsified);
  console.log('VERDICT=FAIL');
  process.exit(1);
}

// ------------------------------------------------------------------- V2 -----
{
  const res = spawnSync(process.execPath, ['--check', INSTRUMENT], { encoding: 'utf8', windowsHide: true });
  check('V2.instrument-parses', res.status === 0, 'node --check exit ' + res.status);
}

// ------------------------------------------------------------------- V3 -----
{
  const res = runInstrument(['--out', join(LOGS, 'usage-no-expect.log'), '--', process.execPath, OK0]);
  check(
    'V3.usage-without-expect',
    res.code === 2 && res.out.includes('usage:'),
    'exit=' + res.code + ' usage_line=' + res.out.includes('usage:')
  );
}

// ------------------------------------------------------------------- V4 -----
{
  const res = runInstrument(['--expect', 'MARKER_BETA', '--', process.execPath, OK0]);
  check(
    'V4.usage-without-out',
    res.code === 2 && res.out.includes('usage:'),
    'exit=' + res.code + ' usage_line=' + res.out.includes('usage:')
  );
}

// ------------------------------------------------------------------- P1 -----
// The inversion: inner exit 2, marker present -> wrapper exit 0.
{
  const res = runInstrument([
    '--out', join(LOGS, 'inversion.log'),
    '--expect-exit', '2',
    '--expect', 'MARKER_ALPHA',
    '--', process.execPath, FAIL2,
  ]);
  const summary = summaryLine(res.out);
  const ok = res.code === 0 && summary === 'EXIT=2 EXPECTED_EXIT=2 MARKERS=1/1 VERDICT=PASS';
  check('P1.inversion-exit2-marker-present', ok, 'wrapper_exit=' + res.code + ' summary="' + summary + '"');
  if (ok) {
    console.log('PROOF inversion: ' + summary + ' wrapper_exit=' + res.code);
  }
}

// ------------------------------------------------------------------- P2 -----
// The gate must block: a missing marker -> wrapper exit 1, marker named.
{
  const res = runInstrument([
    '--out', join(LOGS, 'missing.log'),
    '--expect-exit', '2',
    '--expect', 'MARKER_NOT_PRESENT',
    '--', process.execPath, FAIL2,
  ]);
  const named = res.out.includes('MISSING=MARKER_NOT_PRESENT');
  const ok = res.code === 1 && named;
  check('P2.block-missing-marker', ok, 'wrapper_exit=' + res.code + ' named=' + named);
  if (ok) {
    falsified += 1;
    console.log('PROOF block: MISSING=MARKER_NOT_PRESENT wrapper_exit=' + res.code);
  }
}

// ------------------------------------------------------------------- P3 -----
{
  const res = runInstrument([
    '--out', join(LOGS, 'forbidden.log'),
    '--expect-exit', '2',
    '--expect', 'MARKER_ALPHA',
    '--forbid', 'PROBE_RESULT=COMPLETE',
    '--', process.execPath, FAIL2,
  ]);
  const named = res.out.includes('UNEXPECTED=PROBE_RESULT=COMPLETE');
  const ok = res.code === 1 && named;
  check('P3.block-forbidden-marker', ok, 'wrapper_exit=' + res.code + ' named=' + named);
  if (ok) {
    falsified += 1;
    console.log('PROOF block: UNEXPECTED=PROBE_RESULT=COMPLETE wrapper_exit=' + res.code);
  }
}

// ------------------------------------------------------------------- P4 -----
{
  const res = runInstrument([
    '--out', join(LOGS, 'exit-mismatch.log'),
    '--expect', 'MARKER_ALPHA',
    '--', process.execPath, FAIL2,
  ]);
  const named = res.out.includes('EXIT_MISMATCH got=2 want=0');
  const ok = res.code === 1 && named;
  check('P4.block-exit-mismatch', ok, 'wrapper_exit=' + res.code + ' named=' + named);
  if (ok) {
    falsified += 1;
    console.log('PROOF block: EXIT_MISMATCH got=2 want=0 wrapper_exit=' + res.code);
  }
}

// ------------------------------------------------------------------- P5 -----
{
  const res = runInstrument([
    '--out', join(LOGS, 'command-missing.log'),
    '--expect', 'ANY_MARKER',
    '--', 'bg-verdict-no-such-command-xyz',
  ]);
  const named = res.out.includes('COMMAND_MISSING=');
  const ok = res.code === 1 && named;
  check('P5.command-missing', ok, 'wrapper_exit=' + res.code + ' named=' + named);
  if (ok) {
    falsified += 1;
    console.log('PROOF block: COMMAND_MISSING wrapper_exit=' + res.code);
  }
}

// ------------------------------------------------------------------- P6 -----
{
  const res = runInstrument([
    '--out', join(LOGS, 'accounting.log'),
    '--expect', 'MARKER_BETA',
    '--expect', 'PROBE_RESULT=COMPLETE',
    '--forbid', 'MARKER_ALPHA',
    '--', process.execPath, OK0,
  ]);
  const summary = summaryLine(res.out);
  const ok = res.code === 0 && summary === 'EXIT=0 EXPECTED_EXIT=0 MARKERS=3/3 VERDICT=PASS';
  check('P6.marker-accounting', ok, 'wrapper_exit=' + res.code + ' summary="' + summary + '"');
}

// ------------------------------------------------------------------- P7 -----
// The log must exist and carry the captured output even for a failing run.
{
  const log = join(LOGS, 'log-on-failure.log');
  const res = runInstrument([
    '--out', log,
    '--expect-exit', '2',
    '--expect', 'MARKER_NOT_PRESENT',
    '--', process.execPath, FAIL2,
  ]);
  const exists = existsSync(log);
  let body = '';
  if (exists) body = readFileSync(log, 'utf8');
  const hasOutput = body.includes('MARKER_ALPHA');
  const hasTrailer = body.includes('--- bg-verdict ---') && body.includes('VERDICT=FAIL');
  const ok = res.code === 1 && exists && hasOutput && hasTrailer;
  check(
    'P7.log-written-on-failure',
    ok,
    'exists=' + exists + ' captured_output=' + hasOutput + ' trailer=' + hasTrailer
  );
}

// ------------------------------------------------------------------- P8 -----
// stderr is part of the measurement, not noise to be dropped.
{
  const res = runInstrument([
    '--out', join(LOGS, 'stderr.log'),
    '--expect', 'NOISE_ON_STDERR',
    '--', process.execPath, NOISE,
  ]);
  const ok = res.code === 0 && res.out.includes('NOISE_ON_STDERR');
  check('P8.stderr-captured', ok, 'wrapper_exit=' + res.code + ' stderr_in_output=' + res.out.includes('NOISE_ON_STDERR'));
}

// ------------------------------------------------------------------- P9 -----
// The summary line must keep its exact shape on both verdicts.
{
  const pass = runInstrument([
    '--out', join(LOGS, 'shape-pass.log'),
    '--expect', 'MARKER_BETA',
    '--', process.execPath, OK0,
  ]);
  const fail = runInstrument([
    '--out', join(LOGS, 'shape-fail.log'),
    '--expect', 'MARKER_NOT_PRESENT',
    '--', process.execPath, OK0,
  ]);
  const shape = /^EXIT=-?\d+ EXPECTED_EXIT=-?\d+ MARKERS=\d+\/\d+ VERDICT=(PASS|FAIL)$/m;
  const ok = shape.test(pass.out) && shape.test(fail.out);
  check('P9.summary-line-shape', ok, 'pass_shape=' + shape.test(pass.out) + ' fail_shape=' + shape.test(fail.out));
}

// ------------------------------------------------------------------ P10 -----
// The wrapper's verdict code must never be confused with the usage code.
{
  const fail = runInstrument([
    '--out', join(LOGS, 'codes.log'),
    '--expect', 'MARKER_NOT_PRESENT',
    '--', process.execPath, OK0,
  ]);
  const usage = runInstrument(['--out', join(LOGS, 'codes-usage.log'), '--', process.execPath, OK0]);
  const ok = fail.code === 1 && usage.code === 2;
  check('P10.verdict-code-vs-usage-code', ok, 'verdict_fail_exit=' + fail.code + ' usage_exit=' + usage.code);
}

// ------------------------------------------------------------------ P11 -----
// A pass must never be reported as a failed task: the wrapper exits 0 even
// when the inner command exited non-zero.
{
  const res = runInstrument([
    '--out', join(LOGS, 'no-false-failure.log'),
    '--expect-exit', '2',
    '--expect', 'MARKER_ALPHA',
    '--', process.execPath, FAIL2,
  ]);
  const ok = res.code === 0;
  check('P11.pass-is-not-a-failed-task', ok, 'inner_exit=2 wrapper_exit=' + res.code);
}

// ------------------------------------------------------------------ P12 -----
// Windows reports an exit status as an unsigned 32-bit value: exit(-1) is
// reported as 4294967295. Both spellings must be accepted for the same status.
{
  const neg = writeFixture(
    'probe-neg1.mjs',
    "process.stdout.write('MARKER_NEGATIVE_EXIT\\n');\nprocess.exit(-1);\n"
  );
  const res = runInstrument([
    '--out', join(LOGS, 'negative-exit.log'),
    '--expect-exit', '4294967295',
    '--expect', 'MARKER_NEGATIVE_EXIT',
    '--', process.execPath, neg,
  ]);
  const summary = summaryLine(res.out);
  const ok = res.code === 0 && (summary === 'EXIT=4294967295 EXPECTED_EXIT=4294967295 MARKERS=1/1 VERDICT=PASS' || summary === 'EXIT=255 EXPECTED_EXIT=4294967295 MARKERS=1/1 VERDICT=PASS');
  check('P12.windows-unsigned-exit-status', ok, 'wrapper_exit=' + res.code + ' summary="' + summary + '"');
}

// ------------------------------------------------------------------ P13 -----
// The wrapper must never print the environment of the command.
{
  const sentinel = 'BG_VERDICT_SENTINEL_9c41f0';
  const res = spawnSync(
    process.execPath,
    [INSTRUMENT, '--out', join(LOGS, 'no-env.log'), '--expect', 'MARKER_BETA', '--', process.execPath, OK0],
    {
      encoding: 'utf8',
      windowsHide: true,
      env: Object.assign({}, process.env, { BG_VERDICT_SENTINEL: sentinel }),
    }
  );
  const out = (res.stdout || '') + (res.stderr || '');
  const leaked = out.includes(sentinel);
  const ok = res.status === 0 && !leaked;
  check('P13.environment-not-echoed', ok, 'wrapper_exit=' + res.status + ' sentinel_leaked=' + leaked);
}

console.log('');
console.log(
  'SUMMARY checks=' + checks +
  ' failed=' + defects.length +
  ' warnings=' + warnings +
  ' falsified=' + falsified
);
console.log('VERDICT=' + (defects.length === 0 ? 'PASS' : 'FAIL'));
for (const d of defects) console.log('  - ' + d);
process.exit(defects.length === 0 ? 0 : 1);
