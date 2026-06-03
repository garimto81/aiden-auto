#!/usr/bin/env node
/**
 * Combined statusline wrapper.
 *
 * Splits stdin to three child processes in parallel:
 *   0) aiden-auto-telemetry.mjs → phase · agent · model · pdca · cost · breaker (TOP line)
 *   1) hybrid-statusline.mjs    → existing single-line statusline (preserved)
 *   2) model-usage-line.py      → per-model token + cost lines
 *
 * Outputs all three (top-down), separated by newlines. Silent on any failure.
 * Each child has independent 7s timeout — slow telemetry never blocks hybrid.
 */
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

// __dirname 대체 (ESM)
const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// 같은 디렉토리의 sibling 파일 참조 (이식성 보장)
const HUD_TELEMETRY = join(__dirname, "aiden-auto-telemetry.mjs");
const HUD_NODE      = join(__dirname, "hybrid-statusline.mjs");
const HUD_PY        = join(__dirname, "model-usage-line.py");      // 옛 토큰 덤프 (보존, 미사용)
const HUD_MIX       = join(__dirname, "model-mix-line.mjs");       // 읽기 쉬운 모델 mix (재복귀 2026-06)
const HUD_ATLASSIAN = join(__dirname, "atlassian-auth-line.mjs");
const CHILD_TIMEOUT_MS = 7000;

function readStdin() {
  return new Promise((resolve) => {
    let data = "";
    process.stdin.setEncoding("utf8");
    process.stdin.on("data", (c) => (data += c));
    process.stdin.on("end", () => resolve(data));
    process.stdin.on("error", () => resolve(data));
  });
}

function callChild(cmd, args, input) {
  return new Promise((resolve) => {
    let out = "";
    let settled = false;
    const finish = () => {
      if (settled) return;
      settled = true;
      resolve(out);
    };
    try {
      const p = spawn(cmd, args, { stdio: ["pipe", "pipe", "ignore"] });
      const t = setTimeout(() => {
        try { p.kill(); } catch {}
        finish();
      }, CHILD_TIMEOUT_MS);
      p.stdout.on("data", (d) => (out += d.toString()));
      p.on("close", () => { clearTimeout(t); finish(); });
      p.on("error", () => { clearTimeout(t); finish(); });
      try {
        p.stdin.write(input);
        p.stdin.end();
      } catch { /* child may have died */ }
    } catch {
      finish();
    }
  });
}

async function main() {
  const stdin = await readStdin();
  // 모델 mix 재복귀 (사용자 결정 2026-06): 옛 model-usage-line.py 의 라벨 없는 토큰 덤프 대신
  // model-mix-line.mjs 가 "🤖 Opus N · Sonnet N · Haiku N" 읽기 쉬운 라인 출력.
  // Sonnet/Haiku 가 실제로 라우팅되는지 검증용. HUD_PY(옛 도구) 는 보존하되 미사용.
  const [telemetryOut, hudOut, mixOut, atlassianOut] = await Promise.all([
    callChild("node",   [HUD_TELEMETRY], stdin),
    callChild("node",   [HUD_NODE],      stdin),
    callChild("node",   [HUD_MIX],       stdin),
    callChild("node",   [HUD_ATLASSIAN], stdin),
  ]);
  const lines = [];
  if (telemetryOut) lines.push(telemetryOut.replace(/\s+$/g, ""));
  if (hudOut)       lines.push(hudOut.replace(/\s+$/g, ""));
  if (mixOut)       lines.push(mixOut.replace(/\s+$/g, ""));
  if (atlassianOut) lines.push(atlassianOut.replace(/\s+$/g, ""));
  if (lines.length) process.stdout.write(lines.join("\n") + "\n");
}

main();
