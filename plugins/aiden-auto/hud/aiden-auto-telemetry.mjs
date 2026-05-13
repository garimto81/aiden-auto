#!/usr/bin/env node
/**
 * aiden-auto telemetry single-line statusline.
 *
 * Reads ~/.claude/state/telemetry.json and emits ONE line:
 *   ▸ phase-3 · verify  ⊕ qa-tester  ◆ sonnet-4.5  ↻ pdca 2/5  $ 0.142  ⚡ breaker 0/3
 *
 * Each segment is independent — if a field is missing the segment is skipped.
 * If all fields are missing the script emits nothing (statusline-combined
 * will then drop the empty line).
 *
 * Schema (flat, all fields optional):
 *   {
 *     "phase":      "phase-3",
 *     "step":       "verify",
 *     "agent":      "qa-tester",
 *     "model":      "sonnet-4.5",
 *     "pdca_i":     2,           // current iteration
 *     "pdca_n":     5,           // max iterations
 *     "cost_usd":   0.142,
 *     "breaker_i":  0,
 *     "breaker_n":  3,
 *     "updated_at": "2026-05-13T12:34:56Z"
 *   }
 *
 * Owner: aiden-auto plugin (registered in references/external-harness-registry.md).
 */

import { readFileSync, existsSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

const STATE_PATH = join(homedir(), ".claude", "state", "telemetry.json");

const c = {
  reset:   "\x1b[0m",
  dim:     "\x1b[2m",
  cyan:    "\x1b[36m",
  magenta: "\x1b[35m",
  white:   "\x1b[97m",
  yellow:  "\x1b[33m",
  green:   "\x1b[32m",
  red:     "\x1b[31m",
};

function readStdin() {
  return new Promise((resolve) => {
    let data = "";
    process.stdin.setEncoding("utf8");
    process.stdin.on("data", (d) => (data += d));
    process.stdin.on("end", () => resolve(data));
    process.stdin.on("error", () => resolve(data));
  });
}

function readState() {
  try {
    if (!existsSync(STATE_PATH)) return {};
    const raw = readFileSync(STATE_PATH, "utf8");
    return JSON.parse(raw);
  } catch {
    return {};
  }
}

function fmtPhase(s) {
  if (!s.phase) return null;
  const step = s.step ? ` · ${s.step}` : "";
  return `${c.cyan}▸ ${s.phase}${step}${c.reset}`;
}

function fmtAgent(s) {
  if (!s.agent) return null;
  return `${c.magenta}⊕ ${s.agent}${c.reset}`;
}

function fmtModel(s, modelFromStdin) {
  const m = s.model || modelFromStdin;
  if (!m) return null;
  return `${c.white}◆ ${m}${c.reset}`;
}

function fmtPdca(s) {
  if (s.pdca_i == null || s.pdca_n == null) return null;
  const ratio = s.pdca_n > 0 ? s.pdca_i / s.pdca_n : 0;
  const col = ratio >= 1 ? c.red : ratio >= 0.8 ? c.yellow : c.green;
  return `${col}↻ pdca ${s.pdca_i}/${s.pdca_n}${c.reset}`;
}

function fmtCost(s) {
  if (s.cost_usd == null) return null;
  const v = Number(s.cost_usd).toFixed(3);
  return `${c.yellow}$ ${v}${c.reset}`;
}

function fmtBreaker(s) {
  if (s.breaker_i == null || s.breaker_n == null) return null;
  const ratio = s.breaker_n > 0 ? s.breaker_i / s.breaker_n : 0;
  const col = ratio >= 1 ? c.red : ratio >= 0.67 ? c.yellow : c.green;
  return `${col}⚡ breaker ${s.breaker_i}/${s.breaker_n}${c.reset}`;
}

async function main() {
  try {
    const stdin = await readStdin();
    let stdinObj = {};
    try { stdinObj = JSON.parse(stdin); } catch {}

    // fallback model: pull from CC stdin if state lacks one
    const modelFromStdin =
      stdinObj.model?.display_name ||
      (typeof stdinObj.model === "string" ? stdinObj.model : null) ||
      stdinObj.modelName ||
      null;

    const state = readState();

    const parts = [
      fmtPhase(state),
      fmtAgent(state),
      fmtModel(state, modelFromStdin),
      fmtPdca(state),
      fmtCost(state),
      fmtBreaker(state),
    ].filter(Boolean);

    if (parts.length === 0) return; // silent — statusline-combined drops empty line

    process.stdout.write(parts.join("  "));
  } catch {
    // silent fallback — statusline must never crash CC
  }
}

main();
