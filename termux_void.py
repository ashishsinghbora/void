"""
termux_void.py - High-Performance Interactive CLI Assistant for Void Platform.

Deterministic ReAct reasoning loop with real-time feedback,
error fallback recovery, and low-memory footprint for terminal sessions.
"""

import os
import sys
import json
import logging
import resource

# Prepend Termux binaries path dynamically
PREFIX = os.environ.get("PREFIX", "/data/data/com.termux/files/usr")
TERMUX_BIN_PATH = os.path.join(PREFIX, "bin") if os.path.exists(PREFIX) else "/data/data/com.termux/files/usr/bin"
if os.path.exists(TERMUX_BIN_PATH) and TERMUX_BIN_PATH not in os.environ.get("PATH", ""):
    os.environ["PATH"] = f"{TERMUX_BIN_PATH}{os.pathsep}{os.environ.get('PATH', '')}"

from core.command_executor import IS_TERMUX
from agents.react_agent import global_react_agent
from core.types import AgentResponse

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")


def print_banner():
    usage = resource.getrusage(resource.RUSAGE_SELF)
    rss_mb = round(usage.ru_maxrss / 1024.0, 2)
    print("=" * 65)
    print("  ⚡ VOID REACT CLI HUB (Android/Termux Hardened)")
    print("=" * 65)
    print(f" Environment:  {'Native Android (Termux)' if IS_TERMUX else 'Desktop Simulator'}")
    print(f" Memory RSS:   {rss_mb} MB (Target: < 50MB)")
    print(f" Architecture: Deterministic ReAct State Machine (Void Engine)")
    print("=" * 65)
    print("Commands:")
    print("  - 'show a toast saying Hello'")
    print("  - 'turn on the flashlight' / 'turn off flashlight'")
    print("  - 'check the battery level'")
    print("  - 'vibrate for 1 second'")
    print("  - 'take a photo using camera'")
    print("  - 'exit' or 'quit' to terminate")
    print("-" * 65)


def main():
    print_banner()

    session_id = "cli_session"

    while True:
        try:
            query = input("\nVoid Assistant > ").strip()
            if not query:
                continue

            if query.lower() in ("exit", "quit", "q"):
                print("\nShutting down Void CLI. Goodbye!")
                break

            print("\n[ReAct Agent Deliberating...]")
            response: AgentResponse = global_react_agent.run(query, session_id=session_id)

            # Display ReAct Reasoning & Confidence
            print(f"🧠 Reasoning:  {response.reasoning}")
            if response.confidence is not None:
                print(f"🎯 Confidence: {int(response.confidence * 100)}%")

            # Display Step Details
            if response.steps:
                print("\n📋 Execution Steps:")
                for s in response.steps:
                    action_display = s.action if s.action else "Deliberation"
                    print(f"  • Step {s.step_number} [{s.status.value}] ({s.duration_ms}ms) -> {action_display}")

            # Display Tool Results
            print("\n⚡ Tool Outputs:")
            if response.results:
                for idx, r in enumerate(response.results, 1):
                    if isinstance(r, dict):
                        print(f"  [{idx}] {json.dumps(r, indent=2)}")
                    else:
                        print(f"  [{idx}] {r}")
            else:
                print("  [No tools triggered or low confidence]")

            # Print RSS telemetry
            usage = resource.getrusage(resource.RUSAGE_SELF)
            rss_mb = round(usage.ru_maxrss / 1024.0, 2)
            print(f"\n[Telemetry] Current RAM RSS: {rss_mb} MB | Target Met: {rss_mb < 50.0}")
            print("-" * 65)

        except (KeyboardInterrupt, EOFError):
            print("\nShutting down Void CLI. Goodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error during command execution: {e}")
            print("-" * 65)


if __name__ == "__main__":
    main()
