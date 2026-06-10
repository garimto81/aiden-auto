#!/usr/bin/env node
/**
 * Claude Status Line
 *
 * v8.0.0 - 2026-04-09: 429 rate limit fix — exponential backoff, 5min cache TTL, common module
 * v7.0.0 - 2026-03-05: Per-turn polling with 60s cache TTL
 * v6.0.0 - 2026-03-05: Remove API calls — cache-only reads
 * v5.0.0 - 2026-03-03: Remove OMC dead code
 * v4.0.0 - 2026-02-18: Direct Usage API polling
 *
 * Every turn: read cache → if age > 5min → API call → update cache.
 * API failure: exponential backoff (3→6→12→15min cap).
 * Stale data preserved (stale > no data).
 *
 * Display policy:
 *   fresh (age < 5min) → normal colors
 *   stale (API failed) → dim colors + ~ prefix
 *   expired (resets_at past) → ?% placeholder (dim)
 *   no data at all     → ?% placeholder (dim)
 */

import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { homedir } from "node:os";
import { join, normalize } from "node:path";
import { readCredentials, fetchUsageFromApi, parseUsageResponse, readCache, writeSuccessCache, writeErrorCache } from "./usage-common.mjs";

const colors = {
  reset: "\x1b[0m",
  cyan: "\x1b[36m",
  magenta: "\x1b[35m",
  dim: "\x1b[2m",
  green: "\x1b[32m",
  white: "\x1b[97m",
  yellow: "\x1b[93m",
  red: "\x1b[31m",
  orange: "\x1b[91m",
};

const CACHE_TTL_SUCCESS_MS = 5 * 60 * 1000;   // 5min
const CACHE_TTL_ERROR_MS   = 3 * 60 * 1000;   // 3min base
const CACHE_TTL_MAX_MS     = 15 * 60 * 1000;  // 15min cap
const API_TIMEOUT_MS       = 5 * 1000;         // 5s
const CACHE_PATH = join(homedir(), ".claude/.usage-cache.json");

// --- Stdin ---

function readStdin() {
  return new Promise((resolve) => {
    let data = "";
    process.stdin.setEncoding("utf8");
    process.stdin.on("data", (chunk) => (data += chunk));
    process.stdin.on("end", () => resolve(data));
  });
}

// --- Git helpers ---

function findGitDir(cwd) {
  try {
    let current = normalize(cwd);
    while (current) {
      const gitDir = join(current, ".git");
      if (existsSync(gitDir)) return gitDir;
      const parent = join(current, "..");
      if (normalize(parent) === current) break;
      current = normalize(parent);
    }
    return null;
  } catch {
    return null;
  }
}

function getGitBranch(cwd) {
  try {
    const gitDir = findGitDir(cwd);
    if (!gitDir) return "";
    const headFile = join(gitDir, "HEAD");
    if (!existsSync(headFile)) return "";
    const content = readFileSync(headFile, "utf8").trim();
    if (content.startsWith("ref: refs/heads/")) {
      return content.replace("ref: refs/heads/", "");
    }
    return content.slice(0, 7);
  } catch {
    return "";
  }
}

function getProjectFolder(cwd) {
  try {
    const parts = normalize(cwd).split(/[/\\]/);
    return parts.filter((p) => p).pop() || "";
  } catch {
    return "";
  }
}

// --- Context window ---

function getContextPercent(stdinObj) {
  // 1순위: stdin context_window (CC 가 제공할 때 — 빠름)
  try {
    const ctx = stdinObj.context_window || {};
    const usage = ctx.current_usage || {};
    if (ctx.current_usage) {
      const windowSize = ctx.context_window_size || 200000;
      const total =
        (usage.input_tokens || 0) +
        (usage.cache_read_input_tokens || 0) +
        (usage.cache_creation_input_tokens || 0);
      if (total > 0) return Math.min(100, Math.round((total / windowSize) * 100));
    }
  } catch { /* fall through to transcript */ }

  // 2순위: transcript 의 마지막 main-chain assistant usage 합산 (버전 독립)
  try {
    const tp = stdinObj.transcript_path;
    if (tp && existsSync(tp)) {
      const lines = readFileSync(tp, "utf8").trim().split("\n");
      for (let i = lines.length - 1; i >= 0; i--) {
        let o;
        try { o = JSON.parse(lines[i]); } catch { continue; }
        if (o.isSidechain) continue;               // subagent 컨텍스트 제외
        const u = o.message && o.message.usage;
        if (!u) continue;
        const total =
          (u.input_tokens || 0) +
          (u.cache_read_input_tokens || 0) +
          (u.cache_creation_input_tokens || 0);
        if (total > 0) return Math.min(100, Math.round((total / 200000) * 100));
      }
    }
  } catch { /* silent */ }
  return 0;
}

function getContextColor(percent) {
  if (percent >= 95) return colors.red;
  if (percent >= 85) return colors.orange;
  if (percent >= 70) return colors.yellow;
  return colors.green;
}

// --- Usage cache + polling ---

async function getUsage() {
  const cache = readCache(CACHE_PATH);
  const now = Date.now();
  const age = cache ? now - (cache.timestamp || 0) : Infinity;

  // 1. Fresh success cache
  if (cache?.data && !cache.error && age <= CACHE_TTL_SUCCESS_MS) {
    return { usage: cache.data, stale: false };
  }

  // 2. Error backoff — prevent rapid retries
  if (cache?.lastFailure) {
    const failCount = cache.failureCount || 1;
    const backoffMs = Math.min(
      CACHE_TTL_ERROR_MS * Math.pow(2, failCount - 1),
      CACHE_TTL_MAX_MS
    );
    if (now - cache.lastFailure < backoffMs) {
      return cache?.data
        ? { usage: cache.data, stale: true }
        : { usage: null, stale: true };
    }
  }

  // 3. API call
  const token = readCredentials();
  if (token) {
    const response = await fetchUsageFromApi(token, API_TIMEOUT_MS);
    if (response) {
      const parsed = parseUsageResponse(response);
      if (parsed) {
        writeSuccessCache(CACHE_PATH, parsed);
        return { usage: parsed, stale: false };
      }
    }
    writeErrorCache(CACHE_PATH, cache);  // record failure
  }

  // 4. Stale fallback
  return cache?.data
    ? { usage: cache.data, stale: true }
    : { usage: null, stale: true };
}

// --- Render ---

function getUsageColor(percent, stale) {
  if (stale) return colors.dim;
  if (percent >= 90) return colors.red;
  if (percent >= 70) return colors.yellow;
  return colors.green;
}

function isDataExpired(usage) {
  if (!usage) return true;
  const now = new Date();
  const fiveExpired = usage.fiveHourResetsAt && new Date(usage.fiveHourResetsAt) < now;
  const weekExpired = usage.weeklyResetsAt && new Date(usage.weeklyResetsAt) < now;
  return fiveExpired && weekExpired;
}

function renderUsage(cached) {
  const { usage, stale } = cached;

  if (!usage || isDataExpired(usage)) {
    const c = colors.dim;
    return `5h:${c}?%${colors.reset} | wk:${c}?%${colors.reset}`;
  }

  const fivePct = Math.round(usage.fiveHourPercent);
  const wkPct = Math.round(usage.weeklyPercent);

  const fiveColor = getUsageColor(fivePct, stale);
  const wkColor = getUsageColor(wkPct, stale);

  const prefix = stale ? "~" : "";

  // 연료 카운트다운 — 5시간 quota 가 언제 회복되는지 (% 보다 행동가능)
  const cd = fmtCountdown(usage.fiveHourResetsAt);
  const cdStr = cd ? `${colors.dim}(${cd})${colors.reset}` : "";
  const fivePart = `5h:${fiveColor}${prefix}${fivePct}%${colors.reset}${cdStr}`;
  const wkPart = `wk:${wkColor}${prefix}${wkPct}%${colors.reset}`;

  return `${fivePart} | ${wkPart}`;
}

// reset 시각(ISO) → 남은 시간 "1h23m" / "23m". 과거/부재 → "".
function fmtCountdown(iso) {
  if (!iso) return "";
  const ms = new Date(iso).getTime() - Date.now();
  if (!(ms > 0)) return "";
  const mins = Math.floor(ms / 60000);
  const h = Math.floor(mins / 60), m = mins % 60;
  return h > 0 ? `${h}h${m}m` : `${m}m`;
}

// 자율 목표 진행도 — active-goal*.json(최신) 거울. live goal 만 표시 (ended → 생략).
function getGoalSegment() {
  try {
    const dir = join(homedir(), ".claude", "state");
    if (!existsSync(dir)) return "";
    const files = readdirSync(dir).filter(
      (f) => f.startsWith("active-goal") && f.endsWith(".json")
    );
    if (!files.length) return "";
    let newest = "", newestM = -1;
    for (const f of files) {
      const m = statSync(join(dir, f)).mtimeMs;
      if (m > newestM) { newestM = m; newest = f; }
    }
    const g = JSON.parse(readFileSync(join(dir, newest), "utf8"));
    if (g.ended_at) return "";  // 종료된 goal 은 계기판에 안 띄움 (live goal 만)
    const cycles = Array.isArray(g.cycles_completed) ? g.cycles_completed.length : 0;
    const st = String(g.convergence_status || g.trip_status || "RUNNING");
    const stKr = /ACHIEV|CONVERG|DONE|COMPLETE/i.test(st) ? "달성" : "진행중";
    const cyc = cycles > 0 ? `${cycles}주기·` : "";
    return `${colors.yellow}🎯 ${cyc}${stKr}${colors.reset}`;
  } catch {
    return "";
  }
}

// --- Main ---

async function main() {
  try {
    const stdin = await readStdin();
    let stdinObj = {};
    try {
      stdinObj = JSON.parse(stdin);
    } catch {}

    // Model name
    let modelName = "Claude";
    if (stdinObj.model && typeof stdinObj.model === "object") {
      modelName = stdinObj.model.display_name || "Claude";
    } else if (stdinObj.modelName) {
      modelName = stdinObj.modelName;
    } else if (stdinObj.model && typeof stdinObj.model === "string") {
      modelName = stdinObj.model;
    }

    function shortenModel(name) {
      const m = name.toLowerCase();
      if (m.includes("opus")) return "Opus";
      if (m.includes("sonnet")) return "Sonnet";
      if (m.includes("haiku")) return "Haiku";
      return name;
    }
    const modelShort = shortenModel(modelName);
    const modelPart = `${colors.white}${modelShort}${colors.reset}`;

    const cwd =
      stdinObj.workspace?.project_dir ||
      stdinObj.workspace?.current_dir ||
      process.cwd();

    // 1. 자율 목표 진행 + alive (거울 — active-goal 최신, live goal 만)
    const goalPart = getGoalSegment();

    // 2. Usage (cache + 5min TTL polling) + 연료 카운트다운
    const cached = await getUsage();
    const usageStr = renderUsage(cached);

    // 2b. Context window 사용량 (사용자 요청 2026-06-11 재추가 — transcript 기반 계산)
    //     CC 빌트인 표시와 중복될 수 있으나, 본 계기판 줄에서도 명시 표시 요청.
    const ctxPct = getContextPercent(stdinObj);
    const ctxStr = ctxPct > 0
      ? `${colors.dim}ctx:${colors.reset}${getContextColor(ctxPct)}${ctxPct}%${colors.reset}`
      : "";

    // 3. Folder + Branch
    const folder = getProjectFolder(cwd);
    const branch = getGitBranch(cwd);
    const hubStr = [
      folder ? `${colors.cyan}📁 ${folder}${colors.reset}` : "",
      branch ? `${colors.magenta}🌿 ${branch}${colors.reset}` : "",
    ].filter(Boolean).join("  ");

    // 계기판 줄1: 모델 | 🎯목표진행 | 연료 | ctx | 폴더/branch
    const mainParts = [modelPart];
    if (goalPart) mainParts.push(goalPart);
    mainParts.push(usageStr);
    if (ctxStr) mainParts.push(ctxStr);
    if (hubStr) mainParts.push(hubStr);
    console.log(mainParts.join(" | "));
  } catch {
    // silent fallback
  }
}

main();
