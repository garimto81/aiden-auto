#!/usr/bin/env node
/**
 * aiden-auto telemetry line 1 — process chain (v4.1).
 *
 * Reads ~/.claude/state/telemetry-{session_id}.json (per-session isolation)
 * and renders process tag queue:
 *   Reading → Searching → Editing → Deliberating → Bash → Deliberating
 *                                                              ^current
 *
 * session_id is read from CC's stdin JSON. If absent, falls back to
 * telemetry-default.json (single legacy file).
 *
 * Queue is maintained by telemetry_update.py hook on every tool event.
 * Max 6 tags, FIFO drop-oldest. Newest on right.
 *
 * Owner: aiden-auto plugin.
 */

import { readFileSync, existsSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

const STATE_DIR = join(homedir(), ".claude", "state");
const ARROW = " → ";
const c = { reset: "\x1b[0m", cyan: "\x1b[36m", dim: "\x1b[2m" };

function readStdin() {
  return new Promise((resolve) => {
    let data = "";
    process.stdin.setEncoding("utf8");
    process.stdin.on("data", (d) => (data += d));
    process.stdin.on("end", () => resolve(data));
    process.stdin.on("error", () => resolve(data));
  });
}

function safeSession(id) {
  if (!id) return "default";
  const s = String(id).replace(/[^a-zA-Z0-9_-]/g, "_");
  return s || "default";
}

function statePath(sessionId) {
  return join(STATE_DIR, `telemetry-${safeSession(sessionId)}.json`);
}

function readState(path) {
  try {
    if (!existsSync(path)) return {};
    return JSON.parse(readFileSync(path, "utf8"));
  } catch {
    return {};
  }
}

async function main() {
  const stdin = await readStdin();
  let stdinObj = {};
  try { stdinObj = JSON.parse(stdin); } catch {}
  const sessionId = stdinObj.session_id || stdinObj.sessionId || null;

  const state = readState(statePath(sessionId));
  const queue = Array.isArray(state.processes) ? state.processes : [];
  if (queue.length === 0) return;

  // stale 가드: 갱신이 오래되면 진행 신호 신뢰 불가 → 마지막 태그를 cyan(진행중)으로
  // 안 칠하고 dim + "·유휴?" 표기. ("진행중인데 끝난 것처럼" / "끝났는데 진행중처럼" 오신호 완화)
  const STALE_MS = 10 * 60 * 1000; // 10분
  let stale = false;
  if (state.updated_at) {
    const age = Date.now() - new Date(state.updated_at).getTime();
    if (Number.isFinite(age) && age > STALE_MS) stale = true;
  }
  const last = queue.length - 1;
  const colored = queue.map((tag, i) =>
    i === last
      ? (stale ? `${c.dim}${tag}${c.reset}` : `${c.cyan}${tag}${c.reset}`)
      : `${c.dim}${tag}${c.reset}`
  );
  let out = colored.join(ARROW);
  if (stale) out += `${c.dim} ·유휴?${c.reset}`;
  process.stdout.write(out);
}

main();
