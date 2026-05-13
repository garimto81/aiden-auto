"""adapters/__init__.py — v28.2 Section 13.2 Adapter Layer registry

격리 패턴: 외부 framework API의 schema 변화가 aiden-auto 코어에 새지 않도록 adapter 각자 격리.
각 adapter는 SUPPORTED_VERSIONS 매트릭스 명시 + feature detection 패턴 사용.

Schema version: 1.0
"""
from __future__ import annotations

import importlib
from typing import Any

SCHEMA_VERSION = "1.0"

# Adapter registry — 호환성 매트릭스
ADAPTER_REGISTRY = {
    "goal": {
        "module": "lib.adapters.goal_adapter",
        "supported_versions": ["2.0+"],  # CC /goal supported in 2.x+
        "fallback": "executor_only",
    },
    "advisor_tool": {
        "module": "lib.adapters.advisor_tool_adapter",
        "supported_versions": ["beta-2026-03-01"],
        "fallback": "executor_only_verdict",
    },
    "agent_view": {
        "module": "lib.adapters.agent_view_adapter",
        "supported_versions": ["2.1.139+"],
        "fallback": "orchestrator_direct",
    },
    "orchestrator": {
        "module": "lib.adapters.orchestrator_adapter",
        "supported_versions": ["v10.3+"],
        "fallback": "single_session",
    },
}


def get_adapter(name: str) -> Any:
    """Lazy load adapter module by name. Returns module or None if unavailable."""
    if name not in ADAPTER_REGISTRY:
        return None
    try:
        return importlib.import_module(ADAPTER_REGISTRY[name]["module"])
    except ImportError:
        return None


def health_check() -> dict:
    """Section 13.1: startup-time compat matrix verify. Returns per-adapter status."""
    status = {}
    for name, meta in ADAPTER_REGISTRY.items():
        try:
            mod = importlib.import_module(meta["module"])
            ok = hasattr(mod, "SUPPORTED_VERSIONS")
            status[name] = {
                "available": ok,
                "supported_versions": getattr(mod, "SUPPORTED_VERSIONS", meta["supported_versions"]),
                "fallback": meta["fallback"],
            }
        except ImportError:
            status[name] = {
                "available": False,
                "supported_versions": meta["supported_versions"],
                "fallback": meta["fallback"],
                "error": "module not loadable",
            }
    return {"schema_version": SCHEMA_VERSION, "adapters": status}


if __name__ == "__main__":
    import json
    print(json.dumps(health_check(), indent=2, ensure_ascii=False))
