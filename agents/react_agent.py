"""
agents/react_agent.py - Autonomous Deterministic ReAct (Reason + Act + Observe) Loop.

Orchestrates multi-step reasoning, dynamic tool execution, hardware error recovery,
and real-time event streaming for the Void agentic platform.
"""

import time
import asyncio
import logging
from typing import Dict, Any, List, Optional

from core.types import AgentState, ReActStep, AgentResponse, ToolExecutionResult
from core.event_bus import global_event_bus
from security.sanitizer import InputSanitizer
from tools.registry import global_tool_registry, ToolRegistry
from storage.repository import ConversationRepository, ExecutionLogRepository
from agents.prompt_processor import PromptPreprocessor
from agents.fallback_handler import HardwareFallbackHandler

logger = logging.getLogger("VoidAdvancedCore.ReActAgent")

try:
    import needle
    HAS_NEEDLE = True
except ImportError:
    needle = None
    HAS_NEEDLE = False


class AutonomousReActAgent:
    """
    Deterministic ReAct Agent implementing Reason -> Act -> Observe execution cycles
    with bounded step guarantees and hardware error feedback loops.
    """
    __slots__ = (
        "_llm_agent",
        "_registry",
        "_event_bus",
        "_convo_repo",
        "_log_repo",
        "_max_steps",
    )

    def __init__(
        self,
        tool_registry: ToolRegistry = global_tool_registry,
        max_steps: int = 5,
    ):
        self._registry = tool_registry
        self._event_bus = global_event_bus
        self._convo_repo = ConversationRepository()
        self._log_repo = ExecutionLogRepository()
        self._max_steps = max_steps
        self._llm_agent = None

        # Discover and bind modular dynamic extensions
        try:
            from extensions.manager import global_extension_manager
            global_extension_manager.discover_and_load_all()
        except Exception as e:
            logger.warning(f"Extension discovery warning: {e}")

        self._init_llm_model()

    def _init_llm_model(self) -> None:
        """Initializes the local LLM runtime with bound tools."""
        if not HAS_NEEDLE or needle is None:
            logger.warning("Local LLM package not available in environment. Running in heuristic ReAct mode.")
            return

        try:
            callables = self._registry.create_needle_callables()
            logger.info(f"Binding {len(callables)} tool strategies to Void LLM...")
            self._llm_agent = needle.Needle(tools=callables)
            logger.info("Void LLM model loaded and bound successfully.")
        except Exception as e:
            logger.error(f"Failed to bind local LLM runtime: {e}")
            self._llm_agent = None

    def run(self, query: str, session_id: str = "default") -> AgentResponse:
        """
        Executes synchronous multi-step ReAct agent deliberation loop.
        Guarantees loop termination within max_steps.
        """
        start_time = time.perf_counter()
        clean_query = PromptPreprocessor.preprocess(query)
        if not clean_query:
            return AgentResponse(
                status="error",
                query=query,
                reasoning="Empty query provided.",
                confidence=0.0,
                results=[],
                steps=[],
                error="Query string cannot be empty.",
            )

        self._event_bus.publish("react_started", {"session_id": session_id, "query": clean_query})
        steps: List[ReActStep] = []
        accumulated_results: List[Any] = []
        final_reasoning = ""
        confidence = 0.95

        step_count = 1

        # Step 1: Deliberation & Initial Model Execution
        step_start = time.perf_counter()
        thought = f"Received query: '{clean_query}'. Evaluating intent and matching hardware tool strategy."
        self._event_bus.publish("react_thought", {"step": step_count, "thought": thought})

        if self._llm_agent is not None:
            try:
                # Invoke local model
                model_res = self._llm_agent.run(clean_query)
                final_reasoning = model_res.get("reasoning", "Processed intent through Void LLM.")
                confidence = model_res.get("confidence") or 0.95
                model_results = model_res.get("results") or []

                for r in model_results:
                    accumulated_results.append(r)

                step_duration = round((time.perf_counter() - step_start) * 1000, 2)
                initial_step = ReActStep(
                    step_number=step_count,
                    thought=final_reasoning,
                    action="void_llm_execution",
                    action_input={"query": clean_query},
                    observation=str(model_results),
                    status=AgentState.OBSERVING,
                    duration_ms=step_duration,
                )
                steps.append(initial_step)
                self._log_repo.log_step(
                    session_id=session_id,
                    step=step_count,
                    tool_name="void_llm_execution",
                    tool_input={"query": clean_query},
                    observation=str(model_results),
                    status=AgentState.OBSERVING.value,
                    duration_ms=step_duration,
                )

                # Check if any tool result reported an error string needing fallback
                for res_item in model_results:
                    res_str = str(res_item)
                    if "Error" in res_str or "failed" in res_str.lower():
                        step_count += 1
                        if step_count <= self._max_steps:
                            fallback_step = self._attempt_fallback(
                                session_id=session_id,
                                step_number=step_count,
                                error_str=res_str,
                            )
                            if fallback_step:
                                steps.append(fallback_step)
                                accumulated_results.append(fallback_step.observation)

            except Exception as e:
                logger.error(f"Void model run failed: {e}")
                final_reasoning = f"Local model execution encountered error: {str(e)}"
                confidence = 0.2
        else:
            # Heuristic intent parser fallback if model binary is not loaded
            heuristic_step = self._execute_heuristic_intent(clean_query, session_id, step_count)
            steps.append(heuristic_step)
            final_reasoning = heuristic_step.thought
            if heuristic_step.observation:
                accumulated_results.append(heuristic_step.observation)

        # Record conversation interaction into SQLite WAL
        self._convo_repo.add_message(
            session_id=session_id,
            role="user",
            content=clean_query,
        )
        self._convo_repo.add_message(
            session_id=session_id,
            role="assistant",
            content=str(accumulated_results),
            reasoning=final_reasoning,
            confidence=confidence,
        )

        response = AgentResponse(
            status="success" if accumulated_results else "no_action",
            query=clean_query,
            reasoning=final_reasoning,
            confidence=confidence,
            results=accumulated_results,
            steps=steps,
            error=None,
        )

        self._event_bus.publish("react_completed", response.to_dict())
        return response

    def _attempt_fallback(self, session_id: str, step_number: int, error_str: str) -> Optional[ReActStep]:
        """Evaluates hardware error and executes deterministic alternative fallback."""
        start = time.perf_counter()
        logger.info(f"Triggering ReAct error feedback evaluation for: '{error_str}'")

        # Map error to source tool
        inferred_tool = "unknown"
        if "camera" in error_str.lower():
            inferred_tool = "take_camera_photo"
        elif "sms" in error_str.lower():
            inferred_tool = "send_sms"
        elif "call" in error_str.lower() or "dial" in error_str.lower():
            inferred_tool = "make_phone_call"
        elif "tts" in error_str.lower() or "speech" in error_str.lower():
            inferred_tool = "text_to_speech"

        decision = HardwareFallbackHandler.evaluate(inferred_tool, {}, error_str)

        thought = f"Observation indicates failure: {error_str}. Fallback evaluation: {decision.remediation_advice}"
        self._event_bus.publish("react_thought", {"step": step_number, "thought": thought})

        if decision.should_fallback and decision.fallback_tool_name:
            # Execute alternative fallback tool
            fallback_res = self._registry.execute(decision.fallback_tool_name, **decision.fallback_arguments)
            elapsed = round((time.perf_counter() - start) * 1000, 2)
            obs = f"[Fallback Executed: {decision.fallback_tool_name}] Output: {fallback_res.output or fallback_res.error}. Advice: {decision.remediation_advice}"

            step = ReActStep(
                step_number=step_number,
                thought=thought,
                action=decision.fallback_tool_name,
                action_input=decision.fallback_arguments,
                observation=obs,
                status=AgentState.RETRYING if not fallback_res.success else AgentState.COMPLETED,
                duration_ms=elapsed,
            )
            self._log_repo.log_step(
                session_id=session_id,
                step=step_number,
                tool_name=decision.fallback_tool_name,
                tool_input=decision.fallback_arguments,
                observation=obs,
                status=step.status.value,
                duration_ms=elapsed,
            )
            return step

        elapsed = round((time.perf_counter() - start) * 1000, 2)
        step = ReActStep(
            step_number=step_number,
            thought=thought,
            action=None,
            action_input=None,
            observation=f"Action required: {decision.remediation_advice}",
            status=AgentState.FAILED,
            duration_ms=elapsed,
        )
        self._log_repo.log_step(
            session_id=session_id,
            step=step_number,
            tool_name="fallback_evaluation",
            tool_input={},
            observation=step.observation,
            status=step.status.value,
            duration_ms=elapsed,
        )
        return step

    def _execute_heuristic_intent(self, query: str, session_id: str, step_number: int) -> ReActStep:
        """Zero-latency keyword intent matcher when LLM weights are offline."""
        start = time.perf_counter()
        q = query.lower()

        tool_name = None
        args: Dict[str, Any] = {}
        thought = f"Analyzing intent for '{query}' using local routing table."

        if "battery" in q:
            tool_name = "get_battery_status"
        elif "torch" in q or "flashlight" in q:
            tool_name = "set_torch"
            args = {"on": "off" not in q}
        elif "vibrate" in q:
            tool_name = "vibrate_device"
            args = {"duration_ms": 500}
        elif "location" in q or "where am i" in q:
            tool_name = "get_location"
        elif "wifi" in q:
            tool_name = "get_wifi_info"
        elif "clipboard" in q:
            tool_name = "get_clipboard"
        elif "toast" in q:
            tool_name = "show_toast"
            args = {"message": query}
        elif "photo" in q or "camera" in q:
            tool_name = "take_camera_photo"
        elif any(k in q for k in ("crypto", "bitcoin", "btc", "ethereum", "eth", "solana", "sol")):
            tool_name = "track_crypto"
            coin = "bitcoin"
            for c in ("solana", "sol", "ethereum", "eth", "dogecoin", "doge", "ripple", "xrp", "bitcoin", "btc"):
                if c in q:
                    coin = c
                    break
            args = {"coin": coin, "speak": any(s in q for s in ("speak", "say", "tell"))}
        elif any(k in q for k in ("github", "repo", "repository", "pull request", "pr", "issue")):
            tool_name = "monitor_github"
            check_type = "issues" if any(s in q for s in ("issue", "pr", "bug")) else "summary"
            args = {"repo": "ashishsinghbora/void", "check_type": check_type}
        elif any(k in q for k in ("clean", "cleanup", "cache", "free space", "temp files", "storage")):
            tool_name = "clean_system"
            args = {"dry_run": "force" not in q and "delete" not in q}
        else:
            tool_name = "get_battery_status"

        res: ToolExecutionResult = self._registry.execute(tool_name, **args)
        elapsed = round((time.perf_counter() - start) * 1000, 2)

        obs = str(res.output if res.success else res.error)
        step = ReActStep(
            step_number=step_number,
            thought=thought,
            action=tool_name,
            action_input=args,
            observation=obs,
            status=AgentState.COMPLETED if res.success else AgentState.FAILED,
            duration_ms=elapsed,
        )
        self._log_repo.log_step(
            session_id=session_id,
            step=step_number,
            tool_name=tool_name,
            tool_input=args,
            observation=obs,
            status=step.status.value,
            duration_ms=elapsed,
        )
        return step

    async def run_async(self, query: str, session_id: str = "default") -> AgentResponse:
        """Asynchronous wrapper ensuring main event loop remains non-blocking."""
        return await asyncio.to_thread(self.run, query, session_id)


# Global singleton agent
global_react_agent = AutonomousReActAgent()
