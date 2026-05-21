#!/usr/bin/env node
/**
 * Atlassian MCP Auth statusline line.
 *
 * Reads ~/.claude/state/atlassian-auth-decisions-{date}.json and shows the
 * latest verdict. Silent (empty stdout) when verdict is PASS_THROUGH, DEFER,
 * or file missing — keeps statusline clean for normal operation.
 *
 * Pairs with: ~/.claude/agents/meta/atlassian-auth-executor.md
 * Hook: ~/.claude/hooks/atlassian_auth.py
 */
import { readFileSync, existsSync } from "node:fs";
import { join } from "node:path";
import { homedir } from "node:os";

const VISIBLE_VERDICTS = {
  AUTO_REFRESH: { label: "Atlassian: Refresh", color: "\x1b[33m" },         // yellow
  PROMPT_USER:  { label: "Atlassian: Auth needed (/mcp)", color: "\x1b[31m" }, // red
  BLOCK:        { label: "Atlassian: Blocked", color: "\x1b[90m" },          // grey
  BLOCKED_BY_BREAKER: { label: "Atlassian: Breaker tripped", color: "\x1b[31m" },
  HOOK_ERROR:   { label: "Atlassian: hook error", color: "\x1b[90m" },
};
const RESET = "\x1b[0m";

function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

function loadLatestVerdict() {
  const stateDir = join(homedir(), ".claude", "state");
  const path = join(stateDir, `atlassian-auth-decisions-${todayIso()}.json`);
  if (!existsSync(path)) return null;
  try {
    const data = JSON.parse(readFileSync(path, "utf8"));
    const entries = Array.isArray(data.entries) ? data.entries : [];
    if (entries.length === 0) return null;
    return entries[entries.length - 1];
  } catch {
    return null;
  }
}

function main() {
  const latest = loadLatestVerdict();
  if (!latest) return; // silent
  const verdict = latest.verdict;
  const visible = VISIBLE_VERDICTS[verdict];
  if (!visible) return; // PASS_THROUGH / DEFER / etc. → silent
  // Drain stdin so parent doesn't hang on EPIPE
  process.stdin.resume();
  process.stdin.on("data", () => {});
  process.stdin.on("end", () => {
    process.stdout.write(`${visible.color}${visible.label}${RESET}\n`);
  });
}

main();
