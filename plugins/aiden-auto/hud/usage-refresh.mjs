#!/usr/bin/env node
/**
 * Usage Cache Refresher
 *
 * v8.0.0 - 2026-04-09: Use common module, writeSuccessCache
 *
 * SessionStart hook에서 실행. API를 호출해 ~/.claude/.usage-cache.json을 갱신.
 * statusline에서는 이 캐시 파일만 읽는다 (API 호출 없음).
 *
 * 실패 시 기존 캐시를 보존한다 (stale data > no data).
 */

import { existsSync, mkdirSync } from "node:fs";
import { homedir } from "node:os";
import { join, dirname } from "node:path";
import { readCredentials, fetchUsageFromApi, parseUsageResponse, writeSuccessCache } from "./usage-common.mjs";

async function main() {
  const token = readCredentials();
  if (!token) {
    // No credentials — don't overwrite existing cache
    process.exit(0);
  }

  const response = await fetchUsageFromApi(token, 10000); // hook — 10s timeout
  if (!response) {
    // API failed — preserve existing cache (stale > nothing)
    process.exit(0);
  }

  const usage = parseUsageResponse(response);
  if (!usage) {
    process.exit(0);
  }

  // Write cache
  const cachePath = join(homedir(), ".claude/.usage-cache.json");
  writeSuccessCache(cachePath, usage);
}

main();