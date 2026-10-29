#!/usr/bin/env node
/**
 * bg-verdict.mjs - run a measurement and judge it by WHAT IT PRINTED.
 *
 * The exit code of a compound shell command is not a verdict. A measurement's
 * verdict is the MARKERS in its output. This wrapper makes that mechanical:
 * it runs one command, keeps the whole captured output, checks the markers,
 * and exits 0 when the measurement produced what it was supposed to produce -
 * even when the inner command exited non-zero (that is how a falsification
 * probe is meant to run).
 *
 * Contract:
 *   node bg-verdict.mjs --out <logfile> --expect "<marker>" [--expect "<marker>"]...
 *        [--forbid "<marker>"]... [--expect-exit <code>] -- <command> [args...]
 *
 * Exit codes of THIS wrapper:
 *   0  the verdict is PASS
 *   1  the verdict is FAIL
 *   2  wrong usage (you called me wrong) - a code distinct from the verdict
 *
 * Rules:
 *   - stdout AND stderr are captured, echoed to the console, and written whole
 *     to <logfile>. The log also carries a `--- bg-verdict ---` trailer with
 *     the same summary line the console prints.
 *   - markers are plain substrings, never regular expressions.
 *   - without --expect-exit, an exit code of 0 is required.
 *   - the environment of the command is never echoed and never printed.
 */

import { spawn } from 'node:child_process';
import { writeFileSync, mkdirSync } from 'node:fs';
import { dirname } from 'node:path';

const USAGE =
  'usage: node bg-verdict.mjs --out <logfile> --expect "<marker>" [--expect "<marker>"]... ' +
  '[--forbid "<marker>"]... [--expect-exit <code>] -- <command> [args...]';

const EXIT_PASS = 0;
const EXIT_VERDICT_FAIL = 1;
const EXIT_USAGE = 2;
const EXIT_COMMAND_MISSING = 127;

function usageError(msg) {
  console.error('USAGE_ERROR ' + msg);
  console.error(USAGE);
  process.exit(EXIT_USAGE);
}

function parseArgs(argv) {
  const res = {
    out: null,
    expects: [],
    forbids: [],
    expectExit: 0,
    cmd: null,
    cmdArgs: [],
  };
  let i = 0;
  for (; i < argv.length; i += 1) {
    const a = argv[i];
    if (a === '--') {
      i += 1;
      break;
    }
    if (a === '--out') {
      res.out = argv[i + 1];
      i += 1;
    } else if (a.startsWith('--out=')) {
      res.out = a.slice('--out='.length);
    } else if (a === '--expect') {
      res.expects.push(argv[i + 1]);
      i += 1;
    } else if (a.startsWith('--expect=')) {
      res.expects.push(a.slice('--expect='.length));
    } else if (a === '--forbid') {
      res.forbids.push(argv[i + 1]);
      i += 1;
    } else if (a.startsWith('--forbid=')) {
      res.forbids.push(a.slice('--forbid='.length));
    } else if (a === '--expect-exit') {
      res.expectExit = argv[i + 1];
      i += 1;
    } else if (a.startsWith('--expect-exit=')) {
      res.expectExit = a.slice('--expect-exit='.length);
    } else {
      usageError('unknown option "' + a + '" (the command must follow a "--" separator)');
    }
  }
  res.cmd = argv[i] === undefined ? null : argv[i];
  res.cmdArgs = argv.slice(i + 1);
  return res;
}

function canonicalExit(code) {
  if (typeof code !== 'number' || !Number.isFinite(code)) return null;
  if (process.platform === 'win32') {
    if (code >= 0 && code <= 0xffffffff) {
      return code > 0x7fffffff ? code - 0x100000000 : code;
    }
    return code;
  }
  return ((code % 256) + 256) % 256;
}

const args = parseArgs(process.argv.slice(2));

if (!args.out || args.out.length === 0) {
  usageError('--out <logfile> is required');
}
if (args.expects.length === 0) {
  usageError('at least one --expect "<marker>" is required');
}
if (args.cmd === null || args.cmd.length === 0) {
  usageError('a command is required after the "--" separator');
}
for (const m of args.expects) {
  if (typeof m !== 'string' || m.length === 0) {
    usageError('--expect needs a non-empty marker');
  }
}
for (const m of args.forbids) {
  if (typeof m !== 'string' || m.length === 0) {
    usageError('--forbid needs a non-empty marker');
  }
}
const expectedExit = Number(args.expectExit);
if (!Number.isInteger(expectedExit)) {
  usageError('--expect-exit needs an integer exit code');
}

const chunks = [];
let lastEndedWithNewline = true;
let settled = false;

function capture(buf) {
  chunks.push(buf);
  const text = buf.toString('utf8');
  lastEndedWithNewline = text.endsWith('\n');
}

function finish(code, signal, spawnError) {
  if (settled) return;
  settled = true;

  const output = Buffer.concat(chunks).toString('utf8');
  const missing = [];
  const unexpected = [];
  let passed = 0;

  for (const marker of args.expects) {
    if (output.includes(marker)) {
      passed += 1;
    } else {
      missing.push(marker);
    }
  }
  for (const marker of args.forbids) {
    if (output.includes(marker)) {
      unexpected.push(marker);
    } else {
      passed += 1;
    }
  }

  const gotExit = code;
  const gotCanonical = canonicalExit(gotExit);
  const wantCanonical = canonicalExit(expectedExit);
  const exitOk = gotCanonical !== null && gotCanonical === wantCanonical;

  const total = args.expects.length + args.forbids.length;
  const verdict = missing.length === 0 && unexpected.length === 0 && exitOk ? 'PASS' : 'FAIL';

  const details = [];
  for (const marker of missing) details.push('MISSING=' + marker);
  for (const marker of unexpected) details.push('UNEXPECTED=' + marker);
  if (!exitOk) {
    details.push('EXIT_MISMATCH got=' + (gotExit === null ? 'null' : gotExit) + ' want=' + expectedExit);
  }
  if (spawnError) {
    details.push('COMMAND_MISSING=' + args.cmd);
  }
  if (signal) {
    details.push('SIGNAL=' + signal);
  }

  const summary =
    'EXIT=' + (gotExit === null ? 'null' : gotExit) +
    ' EXPECTED_EXIT=' + expectedExit +
    ' MARKERS=' + passed + '/' + total +
    ' VERDICT=' + verdict;

  const trailer =
    '--- bg-verdict ---' + '\n' +
    'COMMAND=' + args.cmd + '\n' +
    details.join('\n') + (details.length ? '\n' : '') +
    summary + '\n';

  try {
    mkdirSync(dirname(args.out), { recursive: true });
    writeFileSync(args.out, output + (output.length && !output.endsWith('\n') ? '\n' : '') + trailer, 'utf8');
  } catch (err) {
    console.error('LOG_WRITE_FAILED ' + (err && err.message ? err.message : String(err)));
  }

  if (!lastEndedWithNewline && output.length > 0) {
    process.stdout.write('\n');
  }
  for (const d of details) console.log(d);
  console.log(summary);

  process.exit(verdict === 'PASS' ? EXIT_PASS : EXIT_VERDICT_FAIL);
}

let child;
try {
  child = spawn(args.cmd, args.cmdArgs, {
    stdio: ['ignore', 'pipe', 'pipe'],
    windowsHide: true,
  });
} catch (err) {
  finish(EXIT_COMMAND_MISSING, null, err);
}

if (child) {
  if (child.stdout) {
    child.stdout.on('data', (buf) => {
      capture(buf);
      process.stdout.write(buf);
    });
  }
  if (child.stderr) {
    child.stderr.on('data', (buf) => {
      capture(buf);
      process.stderr.write(buf);
    });
  }
  child.on('error', (err) => {
    finish(EXIT_COMMAND_MISSING, null, err);
  });
  child.on('close', (code, signal) => {
    finish(code, signal, null);
  });
}
