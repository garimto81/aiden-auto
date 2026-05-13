#!/usr/bin/env node
/**
 * PostToolUse hook — run tests for the file just edited (non-blocking).
 *
 * Contract:
 *   - Triggered after Edit/Write tool calls.
 *   - Reads hook event JSON from stdin (Claude Code hook protocol).
 *   - Locates the edited file, finds its "sibling" test file by language heuristic,
 *     runs that test file only, and prints short feedback to stderr.
 *   - Never blocks: no `decision` field, no non-zero exit that would halt tooling.
 *   - Respects per-project opt-out: .claude/test-profile.json .gates.hooks.post_edit_test_runner = false
 *   - Hard timeout 10s per invocation.
 */

const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

const TIMEOUT_MS = 10_000;

function readStdin() {
  try { return fs.readFileSync(0, 'utf8'); } catch { return ''; }
}

function parseEvent(raw) {
  try { return JSON.parse(raw); } catch { return null; }
}

function extractEditedPath(evt) {
  if (!evt) return null;
  const input = evt.tool_input || evt.toolInput || {};
  return input.file_path || input.path || null;
}

function projectRoot(filePath) {
  // Walk upwards looking for any manifest or .claude/ dir; stop at filesystem root
  let dir = path.dirname(path.resolve(filePath));
  const markers = ['package.json', 'pyproject.toml', 'pubspec.yaml', 'go.mod', 'Cargo.toml', 'Gemfile', '.claude'];
  while (true) {
    for (const m of markers) {
      if (fs.existsSync(path.join(dir, m))) return dir;
    }
    const parent = path.dirname(dir);
    if (parent === dir) return null;
    dir = parent;
  }
}

function readProfile(root) {
  try { return JSON.parse(fs.readFileSync(path.join(root, '.claude', 'test-profile.json'), 'utf8')); }
  catch { return null; }
}

function isOptedOut(profile) {
  return Boolean(profile && profile.gates && profile.gates.hooks
    && profile.gates.hooks.post_edit_test_runner === false);
}

function guessTestSibling(editedAbs, adapter) {
  const ext = path.extname(editedAbs);
  const base = path.basename(editedAbs, ext);
  const dir = path.dirname(editedAbs);

  // If the edited file IS a test file, return itself
  if (/\.(test|spec)\.(ts|js|tsx|jsx|mjs|cjs)$/.test(editedAbs)) return editedAbs;
  if (/_test\.(dart|go)$/.test(editedAbs)) return editedAbs;
  if (/^test_.*\.py$/.test(path.basename(editedAbs))) return editedAbs;

  const candidates = [];
  switch (ext) {
    case '.ts': case '.tsx': case '.js': case '.jsx': case '.mjs': case '.cjs':
      candidates.push(
        path.join(dir, `${base}.test${ext}`),
        path.join(dir, `${base}.spec${ext}`),
        path.join(dir, '__tests__', `${base}.test${ext}`),
      );
      break;
    case '.py':
      candidates.push(
        path.join(dir, `test_${base}.py`),
        path.join(dir, 'tests', `test_${base}.py`),
        path.join(dir, '..', 'tests', `test_${base}.py`),
      );
      break;
    case '.dart':
      // lib/foo.dart ↔ test/foo_test.dart (mirror lib/ path to test/)
      {
        const idx = dir.split(path.sep).lastIndexOf('lib');
        if (idx >= 0) {
          const parts = dir.split(path.sep);
          parts[idx] = 'test';
          candidates.push(path.join(parts.join(path.sep), `${base}_test.dart`));
        }
        candidates.push(path.join(dir, `${base}_test.dart`));
      }
      break;
    case '.go':
      candidates.push(path.join(dir, `${base}_test.go`));
      break;
    case '.rs':
      candidates.push(path.join(dir, '..', 'tests', `${base}.rs`));
      // Inline #[cfg(test)] cannot be isolated; skip file-level running for Rust.
      break;
  }

  for (const c of candidates) {
    const resolved = path.resolve(c);
    if (fs.existsSync(resolved)) return resolved;
  }
  return null;
}

function buildCommand(adapter, testPath, root) {
  const rel = path.relative(root, testPath).replace(/\\/g, '/');
  switch (adapter) {
    case 'vitest':        return `npx vitest run "${rel}"`;
    case 'jest':          return `npx jest "${rel}"`;
    case 'pytest':        return `pytest -q "${rel}"`;
    case 'dart-test':     return `dart test "${rel}"`;
    case 'flutter-test':  return `flutter test "${rel}"`;
    case 'go-test':       return `go test "./${path.dirname(rel)}/..."`;
    case 'rspec':         return `bundle exec rspec "${rel}"`;
    default:              return null;
  }
}

function main() {
  let editedPath = null;
  try {
    const raw = readStdin();
    const evt = parseEvent(raw);
    editedPath = extractEditedPath(evt);
  } catch { /* non-fatal */ }

  if (!editedPath || !fs.existsSync(editedPath)) {
    process.exit(0);
  }

  const root = projectRoot(editedPath);
  if (!root) process.exit(0);

  const profile = readProfile(root);
  if (isOptedOut(profile)) process.exit(0);

  // Lazy-load detect so failures here don't break the hook
  let adapter = 'none';
  try {
    const detectMod = require(path.join(process.env.HOME || process.env.USERPROFILE || '', '.claude', 'lib', 'test-adapter', 'detect.js'));
    adapter = detectMod.detect(root).adapter;
  } catch {
    // fallback: infer from extension
    const ext = path.extname(editedPath);
    adapter = ext === '.py' ? 'pytest'
      : ext === '.dart' ? 'dart-test'
      : ext === '.go' ? 'go-test'
      : ext === '.rs' ? 'cargo-test'
      : /\.(ts|tsx|js|jsx|mjs|cjs)$/.test(ext) ? 'vitest'
      : 'none';
  }

  if (adapter === 'none') process.exit(0);

  const testFile = guessTestSibling(editedPath, adapter);
  if (!testFile) {
    process.stderr.write(`[post_edit_test_runner] ⚠️ 대응 테스트 파일 없음 (${path.basename(editedPath)}). 신규 작성 권장.\n`);
    process.exit(0);
  }

  const cmd = buildCommand(adapter, testFile, root);
  if (!cmd) process.exit(0);

  const res = spawnSync(cmd, {
    cwd: root, shell: true, encoding: 'utf8',
    timeout: TIMEOUT_MS, maxBuffer: 4 * 1024 * 1024,
  });

  if (res.error && res.error.code === 'ETIMEDOUT') {
    process.stderr.write(`[post_edit_test_runner] ⏱ 10s 초과 — 수동 실행 권장: ${cmd}\n`);
    process.exit(0);
  }
  if (res.error) {
    process.stderr.write(`[post_edit_test_runner] 실행 오류: ${res.error.message}\n`);
    process.exit(0);
  }
  const relTest = path.relative(root, testFile);
  if (res.status === 0) {
    process.stderr.write(`[post_edit_test_runner] ✅ ${relTest} 통과\n`);
  } else {
    const tail = (res.stdout || '' + res.stderr || '').split('\n').slice(-8).join('\n');
    process.stderr.write(`[post_edit_test_runner] ❌ ${relTest} 실패 (exit=${res.status}) — Phase 0.5 Act 필요\n${tail}\n`);
  }
  process.exit(0);
}

main();
