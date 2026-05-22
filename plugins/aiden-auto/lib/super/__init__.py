"""aiden-auto super skill compile/sync infrastructure.

Compiles winner + losers SKILL.md into a single self-contained super SKILL.md.
Detects drift in source plugins and re-syncs at build time.

See docs/super/ARCHITECTURE.md for the full design.
"""

__version__ = "1.0.0"

from .absorb_marker_parser import AbsorbMarkerParser, ParsedSection
from .attribution_tracker import AttributionEntry, AttributionTracker
from .checkpoint_manager import Checkpoint, CheckpointManager
from .circuit_breaker_super import CircuitBreakerSuper
from .compiler import Compiler, CompileResult
from .evolution_reporter import EvolutionReporter, ReportSummary
from .evolution_scheduler import EvolutionScheduler, EvolveOutcome
from .harvester import Harvester, HarvestedSkill
from .plugin_marketplace_probe import PluginMarketplaceProbe, PluginVersion
from .smoke_tester import SmokeResult, SmokeTester
from .sync_engine import DriftEntry, DriftReport, SyncEngine
from .tier_classifier import DiffMetrics, Tier, TierClassifier

__all__ = [
    "AbsorbMarkerParser",
    "AttributionEntry",
    "AttributionTracker",
    "Checkpoint",
    "CheckpointManager",
    "CircuitBreakerSuper",
    "Compiler",
    "CompileResult",
    "DiffMetrics",
    "DriftEntry",
    "DriftReport",
    "EvolutionReporter",
    "EvolutionScheduler",
    "EvolveOutcome",
    "Harvester",
    "HarvestedSkill",
    "ParsedSection",
    "PluginMarketplaceProbe",
    "PluginVersion",
    "ReportSummary",
    "SmokeResult",
    "SmokeTester",
    "SyncEngine",
    "Tier",
    "TierClassifier",
]
