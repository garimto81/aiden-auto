#!/usr/bin/env python3
"""
Agent/Skill Usage Analyzer

Analyzes Claude Code logs after each commit to extract Agent/Skill usage,
detect failures, and generate improvement suggestions.

Usage:
    python .claude/scripts/analyze-agent-usage.py
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional


class AgentUsageAnalyzer:
    """Main analyzer class"""

    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.config_path = repo_root / ".claude" / "optimizer-config.json"
        self.config = self.load_config()
        self.log_dir = self.detect_claude_log_dir()

    def load_config(self) -> Dict:
        """Load configuration file"""
        if not self.config_path.exists():
            # Return default config
            return {
                "enabled": True,
                "log_analysis": {"max_log_size_mb": 10, "parse_timeout_seconds": 5},
                "improvement": {
                    "auto_generate": True,
                    "model": "claude-sonnet-4-20250514",
                    "max_suggestions": 5,
                },
                "git_metadata": {
                    "enabled": True,
                    "use_trailer": True,
                    "amend_commit": True,
                },
                "notification": {"console_output": True, "save_to_file": True},
            }

        with open(self.config_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def detect_claude_log_dir(self) -> Optional[Path]:
        """Detect Claude Code log directory based on OS"""
        if os.name == "nt":  # Windows
            appdata = os.getenv("APPDATA")
            if appdata:
                return Path(appdata) / "Claude" / "logs"
        elif sys.platform == "darwin":  # macOS
            home = Path.home()
            return home / "Library" / "Logs" / "Claude"
        else:  # Linux
            home = Path.home()
            return home / ".config" / "Claude" / "logs"

        return None

    def find_latest_log(self) -> Optional[Path]:
        """Find the most recent Claude Code log file"""
        if not self.log_dir or not self.log_dir.exists():
            return None

        log_files = list(self.log_dir.glob("*.log"))
        if not log_files:
            return None

        # Return the most recently modified log file
        return max(log_files, key=lambda p: p.stat().st_mtime)

    def parse_log_file(self, log_path: Path) -> List[Dict]:
        """Parse log file and extract Agent/Skill usage"""
        agent_calls = []

        # Regex patterns (placeholder - will be implemented in Task 2.0)
        # For now, return empty list
        return agent_calls

    def analyze_failures(self, agent_calls: List[Dict]) -> List[Dict]:
        """Analyze failed agent calls"""
        failures = []
        for call in agent_calls:
            if call.get("status") == "failed":
                failures.append(call)
        return failures

    def generate_improvements(self, failures: List[Dict]) -> List[Dict]:
        """Generate improvement suggestions for failures"""
        # Placeholder - will be implemented in Task 4.0
        return []

    def save_improvements(self, improvements: List[Dict]):
        """Save improvement suggestions to file"""
        if not improvements:
            return

        suggestions_file = self.repo_root / ".claude" / "improvement-suggestions.md"
        suggestions_file.parent.mkdir(parents=True, exist_ok=True)

        with open(suggestions_file, "a", encoding="utf-8") as f:
            f.write(f"\n## {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            for improvement in improvements:
                f.write(f"### Failed Agent: {improvement['agent']}\n")
                f.write(f"**Original Prompt**: {improvement['original_prompt']}\n\n")
                f.write(f"**Error**: {improvement['error']}\n\n")
                f.write(f"**Improved Prompt**: {improvement['improved_prompt']}\n\n")
                f.write("---\n\n")

    def add_git_metadata(self, agent_calls: List[Dict]):
        """Add Agent usage metadata to Git commit"""
        if not self.config["git_metadata"]["enabled"]:
            return

        if not agent_calls:
            return

        # Placeholder - will be implemented in Task 5.0
        pass

    def notify(self, failures: List[Dict]):
        """Notify user about failures"""
        if not self.config["notification"]["console_output"]:
            return

        if not failures:
            return

        print("\n⚠️  Agent execution failures detected!")
        for failure in failures:
            print(f"  - Agent: {failure['agent_type']}")
            print(f"    Error: {failure['error']}")
        print("\n💡 See improvement suggestions: .claude/improvement-suggestions.md\n")

    def run(self):
        """Main execution"""
        if not self.config["enabled"]:
            return

        # Find latest log
        log_path = self.find_latest_log()
        if not log_path:
            # No log file found - silently exit
            return

        # Parse log file
        agent_calls = self.parse_log_file(log_path)
        if not agent_calls:
            # No agent calls found - silently exit
            return

        # Analyze failures
        failures = self.analyze_failures(agent_calls)

        # Generate improvements for failures
        if failures:
            improvements = self.generate_improvements(failures)
            self.save_improvements(improvements)
            self.notify(failures)

        # Add Git metadata
        self.add_git_metadata(agent_calls)


def main():
    """Entry point"""
    try:
        repo_root = Path(__file__).parent.parent.parent
        analyzer = AgentUsageAnalyzer(repo_root)
        analyzer.run()
    except Exception as e:
        # Silently fail - don't block the commit
        # Log to file for debugging
        error_log = Path(__file__).parent.parent / "optimizer-error.log"
        with open(error_log, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now()}: {str(e)}\n")


if __name__ == "__main__":
    main()
