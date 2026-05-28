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
import re
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

        # Check file size
        max_size = self.config["log_analysis"]["max_log_size_mb"] * 1024 * 1024
        if log_path.stat().st_size > max_size:
            # Skip if too large
            return agent_calls

        # Regex patterns for log parsing
        # Pattern 1: Task execution start
        task_start_pattern = re.compile(
            r"\[(\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z)?)\].*?"
            r"(?:Task execution started|Starting task|Agent execution|Invoking agent)",
            re.IGNORECASE,
        )

        # Pattern 2: Agent type
        agent_type_pattern = re.compile(
            r'(?:Agent type|agent_type|subagent_type):\s*["\']?([a-zA-Z0-9_-]+)["\']?',
            re.IGNORECASE,
        )

        # Pattern 3: Prompt
        prompt_pattern = re.compile(
            r'(?:Prompt|prompt|description):\s*["\']([^"\']{1,500})["\']', re.IGNORECASE
        )

        # Pattern 4: Task completion
        task_complete_pattern = re.compile(
            r"\[(\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z)?)\].*?"
            r"(?:Task (?:execution )?completed|Agent completed|Finished|Success).*?"
            r"(?:\((\d+\.?\d*)\s*(?:s|sec|seconds?)?\))?",
            re.IGNORECASE,
        )

        # Pattern 5: Task failure
        task_failed_pattern = re.compile(
            r"\[(\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z)?)\].*?"
            r"(?:ERROR|FAILED|Task failed|Agent failed|Exception):\s*(.+)",
            re.IGNORECASE,
        )

        try:
            with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                current_task = None
                lines = []

                for line in f:
                    lines.append(line)

                    # Check for task start
                    start_match = task_start_pattern.search(line)
                    if start_match:
                        if current_task:
                            # Save previous task if not completed
                            agent_calls.append(current_task)

                        current_task = {
                            "timestamp": start_match.group(1),
                            "type": "agent",
                            "agent_type": "unknown",
                            "prompt": "",
                            "parameters": {},
                            "status": "unknown",
                            "duration": 0.0,
                            "error": None,
                        }
                        continue

                    if not current_task:
                        continue

                    # Extract agent type
                    agent_match = agent_type_pattern.search(line)
                    if agent_match:
                        current_task["agent_type"] = agent_match.group(1)

                    # Extract prompt
                    prompt_match = prompt_pattern.search(line)
                    if prompt_match:
                        current_task["prompt"] = prompt_match.group(1)

                    # Check for completion
                    complete_match = task_complete_pattern.search(line)
                    if complete_match:
                        current_task["status"] = "success"
                        if complete_match.group(2):
                            current_task["duration"] = float(complete_match.group(2))
                        agent_calls.append(current_task)
                        current_task = None
                        continue

                    # Check for failure
                    failed_match = task_failed_pattern.search(line)
                    if failed_match:
                        current_task["status"] = "failed"
                        current_task["error"] = failed_match.group(2).strip()
                        agent_calls.append(current_task)
                        current_task = None
                        continue

                # Save last task if exists
                if current_task:
                    agent_calls.append(current_task)

        except Exception as e:
            # Log error but don't fail
            error_log = self.repo_root / ".claude" / "optimizer-error.log"
            with open(error_log, "a", encoding="utf-8") as f:
                f.write(f"{datetime.now()}: Log parsing error: {str(e)}\n")

        return agent_calls

    def analyze_failures(self, agent_calls: List[Dict]) -> List[Dict]:
        """Analyze failed agent calls"""
        failures = []
        for call in agent_calls:
            if call.get("status") == "failed":
                # Classify error cause
                error = call.get("error", "").lower()
                cause = "unknown"

                if any(
                    word in error for word in ["timeout", "timed out", "time limit"]
                ):
                    cause = "timeout"
                elif any(
                    word in error for word in ["not found", "cannot find", "missing"]
                ):
                    cause = "missing_context"
                elif any(
                    word in error for word in ["invalid", "error", "failed to parse"]
                ):
                    cause = "parameter_error"
                elif len(call.get("prompt", "")) < 20:
                    cause = "ambiguous_prompt"
                else:
                    cause = "api_error"

                call["failure_cause"] = cause
                failures.append(call)
        return failures

    def generate_improvements(self, failures: List[Dict]) -> List[Dict]:
        """Generate improvement suggestions for failures"""
        if not self.config["improvement"]["auto_generate"]:
            return []

        improvements = []

        try:
            # Check if anthropic is available
            import anthropic

            client = anthropic.Anthropic()

            for failure in failures[: self.config["improvement"]["max_suggestions"]]:
                prompt_text = f"""이 프롬프트가 Agent 실행에 실패했습니다:

Agent: {failure['agent_type']}
원본 프롬프트: "{failure.get('prompt', 'N/A')}"
실패 원인: {failure.get('failure_cause', 'unknown')}
에러: {failure.get('error', 'N/A')}

더 명확하고 구체적인 프롬프트로 개선해주세요. 개선된 프롬프트만 제공하고, 설명은 생략해주세요."""

                message = client.messages.create(
                    model=self.config["improvement"]["model"],
                    max_tokens=500,
                    messages=[{"role": "user", "content": prompt_text}],
                )

                improved_prompt = message.content[0].text.strip()

                improvements.append(
                    {
                        "agent": failure["agent_type"],
                        "original_prompt": failure.get("prompt", ""),
                        "error": failure.get("error", ""),
                        "failure_cause": failure.get("failure_cause", "unknown"),
                        "improved_prompt": improved_prompt,
                    }
                )

        except ImportError:
            # anthropic not installed - skip
            pass
        except Exception as e:
            # Log error but don't fail
            error_log = self.repo_root / ".claude" / "optimizer-error.log"
            with open(error_log, "a", encoding="utf-8") as f:
                f.write(f"{datetime.now()}: Improvement generation error: {str(e)}\n")

        return improvements

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

        if not self.config["git_metadata"]["amend_commit"]:
            return

        try:
            import subprocess

            # Filter out sensitive information
            safe_calls = []
            for call in agent_calls:
                safe_call = {
                    "agent": call.get("agent_type", "unknown"),
                    "status": call.get("status", "unknown"),
                }

                if call.get("duration"):
                    safe_call["duration"] = f"{call['duration']:.1f}s"

                if call.get("status") == "failed" and call.get("failure_cause"):
                    safe_call["error"] = call["failure_cause"]

                safe_calls.append(safe_call)

            # Serialize to JSON (compact)
            usage_json = json.dumps(
                safe_calls, separators=(",", ":"), ensure_ascii=False
            )

            # Get current commit message
            result = subprocess.run(
                ["git", "log", "-1", "--pretty=%B"],
                capture_output=True,
                text=True,
                check=True,
                cwd=self.repo_root,
            )
            current_message = result.stdout.strip()

            # Check if Agent-Usage already exists
            if "Agent-Usage:" in current_message:
                # Already has metadata, skip
                return

            # Append Agent-Usage trailer
            new_message = f"{current_message}\nAgent-Usage: {usage_json}"

            # Amend commit
            subprocess.run(
                ["git", "commit", "--amend", "-m", new_message, "--no-verify"],
                check=True,
                cwd=self.repo_root,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

        except Exception as e:
            # Log error but don't fail
            error_log = self.repo_root / ".claude" / "optimizer-error.log"
            with open(error_log, "a", encoding="utf-8") as f:
                f.write(f"{datetime.now()}: Git metadata error: {str(e)}\n")

    def notify(self, failures: List[Dict]):
        """Notify user about failures"""
        if not self.config["notification"]["console_output"]:
            return

        if not failures:
            return

        try:
            print("\n\u26a0\ufe0f  Agent execution failures detected!")
        except UnicodeEncodeError:
            print("\n[!] Agent execution failures detected!")

        for failure in failures:
            print(f"  - Agent: {failure['agent_type']}")
            print(f"    Error: {failure['error']}")

        try:
            print(
                "\n💡 See improvement suggestions: .claude/improvement-suggestions.md\n"
            )
        except UnicodeEncodeError:
            print(
                "\n[i] See improvement suggestions: .claude/improvement-suggestions.md\n"
            )

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
