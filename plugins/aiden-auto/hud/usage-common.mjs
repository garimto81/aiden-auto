/**
 * Usage API Common Functions
 *
 * v8.0.0 - 2026-04-09: Extracted from hybrid-statusline.mjs & usage-refresh.mjs
 *
 * Shared: readCredentials, fetchUsageOnce, fetchUsageFromApi,
 *         parseUsageResponse, readCache, writeSuccessCache, writeErrorCache
 */

import { existsSync, readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { homedir } from "node:os";
import { join, dirname } from "node:path";
import https from "node:https";

export function readCredentials() {
  try {
    const credPath = join(homedir(), ".claude/.credentials.json");
    if (!existsSync(credPath)) return null;
    const parsed = JSON.parse(readFileSync(credPath, "utf-8"));
    const creds = parsed.claudeAiOauth || parsed;
    if (!creds.accessToken) return null;
    if (creds.expiresAt != null && creds.expiresAt <= Date.now()) return null;
    return creds.accessToken;
  } catch {
    return null;
  }
}

// Single HTTP request — returns { statusCode, retryAfter, data } | null on network error
export function fetchUsageOnce(accessToken, timeoutMs = 5000) {
  return new Promise((resolve) => {
    const req = https.request(
      {
        hostname: "api.anthropic.com",
        path: "/api/oauth/usage",
        method: "GET",
        headers: {
          Authorization: `Bearer ${accessToken}`,
          "anthropic-beta": "oauth-2025-04-20",
          "Content-Type": "application/json",
        },
        timeout: timeoutMs,
      },
      (res) => {
        let data = "";
        res.on("data", (chunk) => (data += chunk));
        res.on("end", () => {
          if (res.statusCode === 200) {
            try { resolve({ statusCode: 200, data: JSON.parse(data) }); }
            catch { resolve(null); }
          } else {
            const ra = parseFloat(res.headers["retry-after"]);
            resolve({ statusCode: res.statusCode, retryAfter: isFinite(ra) ? ra : null, data: null });
          }
        });
      }
    );
    req.on("error", () => resolve(null));
    req.on("timeout", () => { req.destroy(); resolve(null); });
    req.end();
  });
}

export async function fetchUsageFromApi(accessToken, timeoutMs = 5000) {
  const MAX_RETRIES = 1;
  for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
    const result = await fetchUsageOnce(accessToken, timeoutMs);
    if (result === null) return null;                          // network error — no retry
    if (result.statusCode === 200) return result.data;         // success
    if (result.statusCode === 429 && attempt < MAX_RETRIES) {  // rate limited — retry
      const delayMs = Math.max(1000, Math.min((result.retryAfter ?? 1) * 1000, 5000));
      await new Promise((r) => setTimeout(r, delayMs));
      continue;
    }
    return null;                                               // other error — no retry
  }
  return null;
}

export function parseUsageResponse(response) {
  const fiveHour = response.five_hour?.utilization;
  const sevenDay = response.seven_day?.utilization;
  if (fiveHour == null && sevenDay == null) return null;

  const clamp = (v) => (v == null || !isFinite(v)) ? 0 : Math.max(0, Math.min(100, v));
  const parseDate = (s) => {
    if (!s) return null;
    try { const d = new Date(s); return isNaN(d.getTime()) ? null : d; } catch { return null; }
  };

  return {
    fiveHourPercent: clamp(fiveHour),
    weeklyPercent: clamp(sevenDay),
    fiveHourResetsAt: parseDate(response.five_hour?.resets_at),
    weeklyResetsAt: parseDate(response.seven_day?.resets_at),
  };
}

export function readCache(cachePath) {
  try {
    if (!existsSync(cachePath)) return null;
    return JSON.parse(readFileSync(cachePath, "utf-8"));
  } catch {
    return null;
  }
}

export function writeSuccessCache(cachePath, data) {
  try {
    const dir = dirname(cachePath);
    if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
    writeFileSync(cachePath, JSON.stringify({
      timestamp: Date.now(),
      data,
      error: false,
      lastFailure: null,
      failureCount: 0,
    }, null, 2));
  } catch {}
}

export function writeErrorCache(cachePath, existingCache) {
  try {
    const dir = dirname(cachePath);
    if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
    writeFileSync(cachePath, JSON.stringify({
      timestamp: existingCache?.timestamp || Date.now(),
      data: existingCache?.data || null,
      error: true,
      lastFailure: Date.now(),
      failureCount: (existingCache?.failureCount || 0) + 1,
    }, null, 2));
  } catch {}
}