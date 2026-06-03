#!/usr/bin/env node
/**
 * Readable per-model mix statusline line (v1, 2026-06).
 *
 * Re-adds the per-model usage that was deregistered 2026-06-01 — but in a
 * LABELED, readable form. The old model-usage-line.py dumped cryptic numbers
 * ("4.3k 336.8k 50.1m 1.9m|..."); this shows "🤖 Opus 560 · Sonnet 1 · Haiku 12".
 *
 * Answers "am I actually using Sonnet/Haiku?" — reads each assistant message's
 * real `message.model` (what the API billed), across the MAIN transcript and
 * its SUBAGENT transcripts (where dynamic 4:3:3 routing actually happens).
 * The Lead is always Opus, so the Sonnet/Haiku counts are pure subagent routing.
 *
 * Node (no python dep) to match the rest of the statusline + stay portable.
 * Speed: main transcript read incrementally via byte-offset cache; subagent
 * dir re-scanned fresh each turn (small files). Parent enforces 7s timeout.
 * Silent (empty output) on any failure or when there is no data yet.
 *
 * Owner: aiden-auto plugin. Canonical at ~/.claude/hud/.
 */
import {
  existsSync, readFileSync, writeFileSync, mkdirSync, statSync, readdirSync,
} from "node:fs";
import { homedir } from "node:os";
import { join, dirname, basename } from "node:path";

const C = {
  reset: "\x1b[0m",
  dim: "\x1b[2m",
  white: "\x1b[97m",        // opus
  pink: "\x1b[38;5;213m",   // sonnet
  green: "\x1b[92m",        // haiku
};
const CACHE_DIR = join(homedir(), ".claude", ".model-usage-cache");
const TIERS = ["opus", "sonnet", "haiku", "other"];

function readStdin() {
  return new Promise((resolve) => {
    let data = "";
    process.stdin.setEncoding("utf8");
    process.stdin.on("data", (c) => (data += c));
    process.stdin.on("end", () => resolve(data));
    process.stdin.on("error", () => resolve(data));
  });
}

function family(model) {
  const m = (model || "").toLowerCase();
  if (m.includes("opus")) return "opus";
  if (m.includes("haiku")) return "haiku";
  if (m.includes("sonnet")) return "sonnet";
  return "other";
}

function countText(text, counts) {
  for (const line of text.split("\n")) {
    const s = line.trim();
    if (!s) continue;
    let rec;
    try { rec = JSON.parse(s); } catch { continue; }
    if (!rec || rec.type !== "assistant") continue;
    const msg = rec.message || {};
    const t = family(msg.model);
    counts[t] = (counts[t] || 0) + 1;
  }
}

function safeSid(id) {
  if (!id) return "";
  return String(id).replace(/[^a-zA-Z0-9_-]/g, "_");
}

function emptyCounts() {
  return { opus: 0, sonnet: 0, haiku: 0, other: 0 };
}

async function main() {
  const stdin = await readStdin();
  let obj = {};
  try { obj = JSON.parse(stdin); } catch {}

  const tp = obj.transcript_path;
  const sid = safeSid(obj.session_id);
  if (!tp || !existsSync(tp)) return;

  let fileSize = 0;
  try { fileSize = statSync(tp).size; } catch { return; }

  // --- MAIN transcript: incremental (byte-offset cache) ---
  const mainCounts = emptyCounts();
  let startOffset = 0;
  const cachePath = sid ? join(CACHE_DIR, `${sid}.mix.json`) : null;

  if (cachePath && existsSync(cachePath)) {
    try {
      const c = JSON.parse(readFileSync(cachePath, "utf8"));
      // v===1 marker: ignore caches written by other tools / old schema
      if (c && c.v === 1 && typeof c.offset === "number" &&
          c.offset <= fileSize && c.counts) {
        startOffset = c.offset;
        for (const k of TIERS) mainCounts[k] = c.counts[k] || 0;
      }
    } catch {}
  }

  try {
    const buf = readFileSync(tp);
    const chunk = buf.subarray(startOffset).toString("utf8");
    countText(chunk, mainCounts);
  } catch { return; }

  if (cachePath) {
    try {
      if (!existsSync(CACHE_DIR)) mkdirSync(CACHE_DIR, { recursive: true });
      writeFileSync(cachePath, JSON.stringify({ v: 1, offset: fileSize, counts: mainCounts }));
    } catch {}
  }

  // --- SUBAGENT transcripts: fresh full scan (small files, separate from main) ---
  const subCounts = emptyCounts();
  try {
    const stem = basename(tp).replace(/\.jsonl$/, "");
    const subDir = join(dirname(tp), stem, "subagents");
    if (existsSync(subDir)) {
      for (const f of readdirSync(subDir)) {
        if (!f.endsWith(".jsonl")) continue;
        try { countText(readFileSync(join(subDir, f), "utf8"), subCounts); } catch {}
      }
    }
  } catch {}

  const o = mainCounts.opus + subCounts.opus;
  const s = mainCounts.sonnet + subCounts.sonnet;
  const h = mainCounts.haiku + subCounts.haiku;
  if (o + s + h === 0) return;

  const parts = [
    `${C.white}Opus ${o}${C.reset}`,
    `${C.pink}Sonnet ${s}${C.reset}`,
    `${C.green}Haiku ${h}${C.reset}`,
  ];
  process.stdout.write(`🤖 ${parts.join(`${C.dim} · ${C.reset}`)}`);
}

main();
