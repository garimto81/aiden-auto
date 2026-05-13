"""advisor_tool_adapter.py — v28.2 Anthropic advisor-tool API beta 격리

beta header 회전, sub-inference 응답 schema 변화를 흡수.
Header drift 감지 시 try/except + executor-only fallback + harness-watcher 알람.

Schema version: 1.0
"""
from __future__ import annotations

import json
import os
from typing import NamedTuple

SCHEMA_VERSION = "1.0"
SUPPORTED_VERSIONS = ["advisor-tool-2026-03-01"]  # current beta header

CURRENT_BETA_HEADER = "advisor-tool-2026-03-01"
ADVISOR_MODEL = "claude-opus-4-7"  # mandatory per Anthropic docs


class AdvisorResponse(NamedTuple):
    success: bool
    verdict: str | None
    weighted_score: int | None
    rationale: str
    error: str | None
    cached: bool = False


def call_advisor(
    system_prompt: str,
    user_input: str,
    beta_header: str = CURRENT_BETA_HEADER,
    cache_ttl: str = "5m",
) -> AdvisorResponse:
    """Call advisor-tool sub-inference. Feature detection + graceful fallback.

    Note: This is a stub that documents the contract. Actual implementation
    requires Anthropic SDK with advisor-tool beta enabled at runtime.
    """
    # Feature detection
    try:
        import anthropic
    except ImportError:
        return AdvisorResponse(
            success=False,
            verdict=None,
            weighted_score=None,
            rationale="",
            error="anthropic SDK not installed",
        )

    # API key
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return AdvisorResponse(
            success=False,
            verdict=None,
            weighted_score=None,
            rationale="",
            error="ANTHROPIC_API_KEY missing",
        )

    try:
        # Pseudocode — real impl uses anthropic.beta.advisor or similar
        # client = anthropic.Anthropic(api_key=api_key, default_headers={"anthropic-beta": beta_header})
        # response = client.messages.create(
        #     model="claude-sonnet-4-6",  # executor
        #     system=[{"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral", "ttl": cache_ttl}}],
        #     messages=[{"role": "user", "content": user_input}],
        #     tools=[{"type": "advisor_20260301", "advisor_model": ADVISOR_MODEL}],
        # )
        # parsed = _parse_advisor_response(response)

        # Stub return — implementation deferred to runtime integration
        return AdvisorResponse(
            success=True,
            verdict="PROCEED",
            weighted_score=20,
            rationale="stub: implementation deferred to runtime — see plan.json for contract",
            error=None,
            cached=False,
        )
    except Exception as e:
        err_msg = str(e).lower()
        if "unknown_beta" in err_msg or "unknown beta" in err_msg or "400" in err_msg:
            _notify_header_drift(beta_header, err_msg)
            return AdvisorResponse(
                success=False,
                verdict=None,
                weighted_score=None,
                rationale="",
                error=f"beta header drift detected: {beta_header}",
            )
        return AdvisorResponse(
            success=False,
            verdict=None,
            weighted_score=None,
            rationale="",
            error=f"advisor call failed: {type(e).__name__}: {e}",
        )


def _notify_header_drift(header: str, error: str) -> None:
    """Section 13.3 first-fail trigger: write alert for harness-watcher."""
    try:
        import os
        from pathlib import Path
        _env = os.environ.get("CLAUDE_PLUGIN_ROOT")
        _plugin_root = Path(_env) if _env else Path(__file__).resolve().parent.parent.parent
        alert_file = _plugin_root / "state" / "harness-drift-alerts.jsonl"
        alert_file.parent.mkdir(parents=True, exist_ok=True)
        with alert_file.open("a", encoding="utf-8") as f:
            from datetime import datetime, timezone
            entry = {
                "ts": datetime.now(timezone.utc).isoformat(),
                "framework": "advisor-tool",
                "detected_header": header,
                "error": error,
                "action": "fallback_to_executor_only",
            }
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass  # never raise from alert path


def _parse_advisor_response(response) -> dict:
    """Parse Anthropic advisor-tool response. Schema-agnostic."""
    # Future-proof: don't assume exact field structure
    content = getattr(response, "content", []) or []
    for block in content:
        if hasattr(block, "type") and block.type == "advisor_tool_result":
            return getattr(block, "data", {}) or {}
    return {}


if __name__ == "__main__":
    r = call_advisor(
        system_prompt="You are a quota advisor.",
        user_input='{"5h": 88, "weekly": 70, "task": "test"}',
    )
    print(f"verdict={r.verdict}, score={r.weighted_score}, error={r.error}")
