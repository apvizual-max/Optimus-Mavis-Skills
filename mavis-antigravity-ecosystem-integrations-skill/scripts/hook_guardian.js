/**
 * Hook Guardian: Resilient PreToolUse Hook Proxy
 * Prevents non-critical hook failures from blocking Antigravity tool execution.
 */
const { spawnSync } = require('child_process');
const fs = require('fs');
const path = require('path');

function processHooks(hooks) {
    return hooks.filter(h => h.active).map(h => ({
        ...h,
        processedAt: new Date().toISOString(),
        status: 'ready'
    }));
}

if (require.main === module) {
  const logDir = path.join(process.env.USERPROFILE || '', '.gemini', 'antigravity', 'logs');
  if (!fs.existsSync(logDir)) {
    fs.mkdirSync(logDir, { recursive: true });
  }
  const logFile = path.join(logDir, 'hook_guardian.log');

  function log(msg) {
    const ts = new Date().toISOString();
    fs.appendFileSync(logFile, `[${ts}] ${msg}\n`);
  }

  function sanitizePath(p) {
    if (!p) return '';
    return p.replace(/^["']|["']$/g, '').trim();
  }

  const args = process.argv.slice(2);
  let targetScript = '';

  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--target' && i + 1 < args.length) {
      targetScript = sanitizePath(args[i + 1]);
      break;
    }
  }

  if (!targetScript) {
    log('WARN: No target script provided to Hook Guardian. Exiting cleanly.');
    process.exit(0);
  }

  if (!fs.existsSync(targetScript)) {
    log(`WARN: Target script does not exist: ${targetScript}. Suppressing failure to protect agent tool loop.`);
    process.exit(0);
  }

  try {
    const res = spawnSync(process.execPath, [targetScript, ...args.slice(2)], {
      stdio: 'inherit',
      encoding: 'utf-8',
      timeout: 10000
    });

    if (res.error) {
      log(`ERROR: Script execution failed (${targetScript}): ${res.error.message}`);
      process.exit(0); // Never fail the agent tool loop
    }

    process.exit(res.status || 0);
  } catch (err) {
    log(`UNHANDLED: ${err.message}`);
    process.exit(0);
  }
}

module.exports = { processHooks };
