#!/usr/bin/env node
// Cross-platform Python runner for Claude Code hooks.
//
// Why this exists
// - settings.json must be portable across Windows / Linux / macOS.
// - `python3` does not exist on Windows (only a Microsoft Store stub).
// - `python` is Python 2 on legacy systems, Python 3 elsewhere.
// - Hardcoding any single command breaks portability.
//
// What this does
// 1. Detects an interpreter that prints `Python 3.x` for `--version`.
// 2. Skips Microsoft Store stubs (they fail the `--version` probe).
// 3. Forwards stdin/stdout/stderr and exit code transparently.
// 4. Resolves the script path relative to this wrapper's own directory,
//    so settings.json only needs the bare script name.
//
// Usage in settings.json
//   "command": "node ${CLAUDE_PROJECT_DIR}/.claude/hooks/_python_runner.mjs stop_completion_check.py"
//   "command": "node ${CLAUDE_PROJECT_DIR}/.claude/hooks/_python_runner.mjs recovery/edit_error_recovery.py"

import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { dirname, isAbsolute, resolve } from 'node:path';
import { existsSync } from 'node:fs';

const __dirname = dirname(fileURLToPath(import.meta.url));
const [scriptArg, ...extraArgs] = process.argv.slice(2);

if (!scriptArg) {
  console.error('[_python_runner] missing script argument');
  process.exit(0); // non-blocking: do not break the session
}

const scriptPath = isAbsolute(scriptArg) ? scriptArg : resolve(__dirname, scriptArg);
if (!existsSync(scriptPath)) {
  console.error(`[_python_runner] script not found: ${scriptPath}`);
  process.exit(0);
}

const isWindows = process.platform === 'win32';

// Detection order is platform-tuned:
// - Windows: try py launcher first (always picks newest installed Python 3.x),
//   then python (real installer), then python3 (likely Store stub but try anyway).
// - Unix: python3 is canonical; python as fallback for python-is-python3 systems.
const candidates = isWindows
  ? [['py', ['-3']], ['python', []], ['python3', []]]
  : [['python3', []], ['python', []]];

const tried = [];
let chosen = null;

for (const [cmd, prefix] of candidates) {
  const probe = spawnSync(cmd, [...prefix, '--version'], {
    stdio: ['ignore', 'pipe', 'pipe'],
    timeout: 3000,
    encoding: 'utf-8',
    shell: false,
    windowsHide: true,
  });
  const display = [cmd, ...prefix].join(' ');
  if (probe.error?.code === 'ENOENT') {
    tried.push(`${display}: ENOENT`);
    continue;
  }
  if (probe.status !== 0) {
    tried.push(`${display}: exit ${probe.status}`);
    continue;
  }
  const out = `${probe.stdout || ''}${probe.stderr || ''}`;
  if (!/Python\s+3\./.test(out)) {
    tried.push(`${display}: not Python 3 (${out.trim() || 'no output'})`);
    continue;
  }
  chosen = [cmd, prefix];
  break;
}

if (!chosen) {
  console.error('[_python_runner] no Python 3 interpreter found. Tried: ' + tried.join('; '));
  process.exit(0); // non-blocking
}

const [cmd, prefix] = chosen;
const result = spawnSync(cmd, [...prefix, scriptPath, ...extraArgs], {
  stdio: 'inherit',
  shell: false,
  windowsHide: true,
});

if (result.error) {
  console.error(`[_python_runner] failed to launch ${cmd}: ${result.error.message}`);
  process.exit(0);
}

process.exit(result.status ?? 0);
