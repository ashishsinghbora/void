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
        from core.model_manager import global_model_manager
        model_path = global_model_manager.get_active_model_path()
        model_name = global_model_manager.get_active_model_name()

        if not HAS_NEEDLE or needle is None or not model_path:
            if model_path:
                logger.info(f"Detected local model binary at '{model_path}' ({model_name}). Local LLM engine in heuristic bridge mode.")
            else:
                logger.info("Local LLM model offline. Running in deterministic heuristic ReAct mode (<30MB RAM).")
            return

        try:
            callables = self._registry.create_needle_callables()
            logger.info(f"Binding {len(callables)} tool strategies to Void LLM ({model_name})...")
            if hasattr(needle, "Needle"):
                self._llm_agent = needle.Needle(tools=callables, model_path=model_path)
            logger.info("Void LLM model loaded and bound successfully.")
        except Exception as e:
            logger.error(f"Failed to bind local LLM runtime: {e}")
            self._llm_agent = None

    def run(
        self,
        query: str,
        session_id: str = "default",
        thought_callback: Optional[Callable[[int, str], None]] = None,
        action_callback: Optional[Callable[[int, str, Dict[str, Any], str], None]] = None,
    ) -> AgentResponse:
        """
        Executes synchronous multi-step ReAct agent deliberation loop.
        Guarantees loop termination within max_steps and streams live thoughts.
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
                conversational_reply="Hmm, I didn't catch any command in your message. What would you like me to do?",
            )

        self._event_bus.publish("react_started", {"session_id": session_id, "query": clean_query})
        steps: List[ReActStep] = []
        accumulated_results: List[Any] = []
        final_reasoning = ""
        confidence = 0.95

        step_count = 1

        # Step 1: Deliberation & Initial Model Execution
        step_start = time.perf_counter()
        thought = f"Analyzing '{clean_query}' to execute mobile task on device."
        if thought_callback:
            try:
                thought_callback(step_count, thought)
            except Exception:
                pass
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
            heuristic_step = self._execute_heuristic_intent(
                clean_query,
                session_id,
                step_count,
                thought_callback=thought_callback,
                action_callback=action_callback,
            )
            steps.append(heuristic_step)
            final_reasoning = heuristic_step.thought
            if heuristic_step.observation:
                accumulated_results.append(heuristic_step.observation)

        # Generate conversational, talkative response
        conv_reply = format_conversational_reply(clean_query, steps, accumulated_results)

        # Record conversation interaction into SQLite WAL
        self._convo_repo.add_message(
            session_id=session_id,
            role="user",
            content=clean_query,
        )
        self._convo_repo.add_message(
            session_id=session_id,
            role="assistant",
            content=conv_reply,
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
            conversational_reply=conv_reply,
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

    def _execute_heuristic_intent(
        self,
        query: str,
        session_id: str,
        step_number: int,
        thought_callback: Optional[Callable[[int, str], None]] = None,
        action_callback: Optional[Callable[[int, str, Dict[str, Any], str], None]] = None,
    ) -> ReActStep:
        """Zero-latency keyword intent matcher when LLM weights are offline."""
        import re
        start = time.perf_counter()
        q = query.lower()

        tool_name = None
        args: Dict[str, Any] = {}
        thought = f"Analyzing intent for '{query}' using local routing table."

        # 1. Screen Capture & Visuals
        if any(k in q for k in ("screenshot", "screencap", "screen cap", "capture screen")):
            tool_name = "capture_screenshot"
            thought = "Taking a screenshot of the phone display and beaming to Cloud Vault... 📱"

        # 2. Hardware Button Keyevents
        elif any(k in q for k in ("home screen", "go home", "press home", "back to home")):
            tool_name = "mobile_keyevent"
            args = {"key": "home"}
            thought = "Navigating directly to Android Home screen... 🏠"
        elif any(k in q for k in ("go back", "press back", "navigate back", "back button")):
            tool_name = "mobile_keyevent"
            args = {"key": "back"}
            thought = "Triggering Android Back button... 🔙"
        elif any(k in q for k in ("recent apps", "app switcher", "recents", "overview")):
            tool_name = "mobile_keyevent"
            args = {"key": "app_switch"}
            thought = "Opening Android recent apps switcher... 📑"
        elif "volume up" in q:
            tool_name = "mobile_keyevent"
            args = {"key": "volume_up"}
            thought = "Increasing volume level... 🔊"
        elif "volume down" in q:
            tool_name = "mobile_keyevent"
            args = {"key": "volume_down"}
            thought = "Lowering volume level... 🔉"
        elif any(k in q for k in ("lock screen", "power button", "screen lock")):
            tool_name = "mobile_keyevent"
            args = {"key": "power"}
            thought = "Triggering device lock / power toggle... 🔒"

        # 3. Touch Screen Actions (Tap & Swipe)
        elif "tap" in q or "click" in q:
            tap_m = re.search(r"(\d+)[,\s]+(\d+)", query)
            if tap_m:
                tool_name = "mobile_tap"
                args = {"x": int(tap_m.group(1)), "y": int(tap_m.group(2))}
                thought = f"Simulating screen tap at ({args['x']}, {args['y']})... 👆"
            else:
                tool_name = "mobile_keyevent"
                args = {"key": "enter"}
                thought = "Pressing Enter key on screen... ↵"
        elif "swipe" in q:
            tool_name = "mobile_swipe"
            if "up" in q:
                args = {"x1": 540, "y1": 1600, "x2": 540, "y2": 400}
                thought = "Swiping up on mobile screen... ⬆️"
            elif "down" in q:
                args = {"x1": 540, "y1": 400, "x2": 540, "y2": 1600}
                thought = "Swiping down on mobile screen... ⬇️"
            else:
                args = {"x1": 540, "y1": 1000, "x2": 100, "y2": 1000}
                thought = "Swiping across mobile screen... ↔️"

        # 4. Text Input Typing
        elif any(k in q for k in ("type ", "enter text ", "write ")) and not any(k in q for k in ("whatsapp", "telegram")):
            txt_m = re.search(r"(?:type|enter text|write)\s+[\"']?([^\"'\n]+)[\"']?", query, re.IGNORECASE)
            if txt_m:
                tool_name = "mobile_type_text"
                args = {"text": txt_m.group(1).strip()}
                thought = f"Typing \"{args['text']}\" into the active field... ⌨️"

        # 5. Deep Android Settings Screens
        elif "settings" in q and any(s in q for s in ("wifi", "bluetooth", "battery", "display", "sound", "apps", "storage", "security", "accessibility")):
            screen = "wifi"
            for s in ("wifi", "bluetooth", "battery", "display", "sound", "apps", "storage", "security", "accessibility"):
                if s in q:
                    screen = s
                    break
            tool_name = "open_settings_screen"
            args = {"screen": screen}
            thought = f"Navigating to Android {screen.capitalize()} settings screen... ⚙️"

        # 6. In-App Content Search (YouTube, Maps, Google)
        elif "youtube" in q and any(w in q for w in ("play", "song", "video", "search", "watch")):
            term_m = re.search(r"(?:search\s+(?:for\s+)?|play\s+|watch\s+)(.+?)(?:\s+on\s+youtube|\s+in\s+youtube|$)", query, re.IGNORECASE)
            q_term = term_m.group(1).strip() if term_m else query
            tool_name = "search_app_content"
            args = {"app": "youtube", "query": q_term}
            thought = f"Searching YouTube for \"{q_term}\"... ▶️"
        elif "map" in q and "search" in q:
            term_m = re.search(r"search\s+(?:for\s+)?(.+)", query, re.IGNORECASE)
            q_term = term_m.group(1).strip() if term_m else "coffee"
            tool_name = "search_app_content"
            args = {"app": "maps", "query": q_term}
            thought = f"Searching Maps for \"{q_term}\"... 🗺️"

        # 7. Hardware & Media Controls
        elif "battery" in q:
            tool_name = "get_battery_status"
            thought = "Checking device power level and battery temperature... 🔋"
        elif "torch" in q or "flashlight" in q:
            tool_name = "set_torch"
            args = {"on": "off" not in q}
            state = "ON" if args["on"] else "OFF"
            thought = f"Toggling device flashlight {state}... 🔦"
        elif "vibrate" in q:
            tool_name = "vibrate_device"
            args = {"duration_ms": 500}
            thought = "Triggering haptic vibration motor... 📳"
        elif "location" in q or "where am i" in q:
            tool_name = "get_location"
            thought = "Querying GPS coordinates and satellite fix... 📍"
        elif "wifi" in q:
            tool_name = "get_wifi_info"
            thought = "Probing Wi-Fi connection info and RSSI signal... 📶"
        elif "clipboard" in q:
            tool_name = "get_clipboard"
            thought = "Reading current system clipboard text... 📋"
        elif "toast" in q:
            tool_name = "show_toast"
            args = {"message": query}
            thought = f"Showing toast alert: '{query}'... 🍞"
        elif "photo" in q or "camera" in q:
            tool_name = "take_camera_photo"
            thought = "Capturing photo with device camera lens... 📸"
        elif any(k in q for k in ("clean", "cleanup", "cache", "free space", "temp files", "storage")):
            tool_name = "clean_system"
            args = {"dry_run": "force" not in q and "delete" not in q}
            thought = "Sweeping temporary cache and junk files to free storage... 🧹"
        elif "whatsapp" in q:
            tool_name = "send_whatsapp_message"
            phone_match = re.search(r"(\+?\d{7,15})", query)
            phone = phone_match.group(1) if phone_match else "1234567890"
            msg_match = re.search(r"(?:saying|message|text|that)\s+(.+)$", query, re.IGNORECASE)
            msg = msg_match.group(1) if msg_match else "Hello from Void"
            args = {"phone": phone, "message": msg}
            thought = f"Opening WhatsApp chat for +{phone} with message draft... 💬"
        elif "telegram" in q and not q.startswith("/"):
            tool_name = "open_telegram_chat"
            user_match = re.search(r"(?:chat\s+with|to|user|channel)?\s*@?([A-Za-z0-9_]{3,32})", query)
            args = {"username": user_match.group(1) if user_match else "durov"}
            thought = f"Opening Telegram chat for @{args['username']}... ✈️"
        elif any(k in q for k in ("launch", "start app", "open app")):
            tool_name = "launch_installed_app"
            app_match = re.search(r"(?:launch|start|open)\s+(?:app\s+)?([A-Za-z0-9_]+)", query, re.IGNORECASE)
            args = {"app_name": app_match.group(1) if app_match else "settings"}
            thought = f"Launching installed application '{args['app_name']}'... 🚀"
        else:
            tool_name = "get_battery_status"
            thought = "Checking system vitals... 🔋"

        # Stream thought callback
        if thought_callback:
            try:
                thought_callback(step_number, thought)
            except Exception:
                pass
        self._event_bus.publish("react_thought", {"step": step_number, "thought": thought})

        # Stream action callback
        if action_callback and tool_name:
            try:
                action_callback(step_number, tool_name, args, thought)
            except Exception:
                pass

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


def format_conversational_reply(query: str, steps: List[ReActStep], results: List[Any]) -> str:
    """
    Synthesizes a conversational, witty, and transparent reply describing the actions
    executed on the Android device, avoiding dry raw dumps.
    """
    if not steps:
        return f"I took a look at '{query}', but didn't execute any hardware actions. Let me know what you'd like me to control or inspect!"

    # Check if all steps failed
    all_failed = all(s.status == AgentState.FAILED for s in steps)
    if all_failed:
        last_step = steps[-1]
        return f"⚠️ I encountered an issue while trying to handle that: {last_step.observation or 'Device command failed'}. Let me know if you'd like me to retry or try a fallback!"

    # Extract primary successful step
    primary_step = next((s for s in reversed(steps) if s.status == AgentState.COMPLETED), steps[0])
    action = primary_step.action or ""
    action_in = primary_step.action_input or {}
    obs = primary_step.observation or ""

    # Generate friendly conversational responses for mobile tools
    if action == "get_battery_status":
        import json
        try:
            data = json.loads(obs) if isinstance(obs, str) and obs.startswith("{") else {}
            pct = data.get("percentage", "unknown")
            status = data.get("status", "discharging")
            temp = data.get("temperature", "")
            temp_str = f" at {temp}°C" if temp else ""
            plugged = data.get("plugged", "unplugged")
            return f"🔋 Your battery is currently sitting at **{pct}%** ({status}, {plugged}{temp_str}). Device power levels are looking great!"
        except Exception:
            return f"🔋 Checked your battery vitals: {obs}"

    elif action == "capture_screen":
        path = action_in.get("output_path", "Vault/Screenshots")
        return f"📸 Screenshot captured successfully! Saved to `{path}` and mirrored to your cloud vault. Screen looks pristine!"

    elif action == "take_camera_photo":
        cam = action_in.get("camera_id", "back")
        return f"📷 Snapped a crisp photo using camera #{cam}! The image has been saved to your centralized media vault."

    elif action == "mobile_tap":
        x, y = action_in.get("x", 0), action_in.get("y", 0)
        return f"👆 Tapped on the screen at coordinates `({x}, {y})`. Done and dusted!"

    elif action == "mobile_swipe":
        x1, y1 = action_in.get("x1", 0), action_in.get("y1", 0)
        x2, y2 = action_in.get("x2", 0), action_in.get("y2", 0)
        dur = action_in.get("duration_ms", 300)
        return f"👉 Swiped smoothly from `({x1}, {y1})` to `({x2}, {y2})` over {dur}ms."

    elif action == "mobile_keyevent":
        key = action_in.get("key", "HOME")
        return f"🔘 Simulated hardware key event: **{key}**."

    elif action == "mobile_type_text":
        text = action_in.get("text", "")
        return f"⌨️ Typed out: \"{text}\" on your device."

    elif action == "open_settings_screen":
        screen = action_in.get("screen", "main")
        return f"⚙️ Opened Android Settings: **{screen}** screen."

    elif action == "app_search":
        target = action_in.get("target_app", "google")
        q_term = action_in.get("search_query", "")
        return f"🔍 Launched {target.title()} and searched for: *\"{q_term}\"*!"

    elif action == "open_whatsapp_chat":
        phone = action_in.get("phone", "")
        return f"💬 Opened WhatsApp conversation for **+{phone}** with your draft."

    elif action == "open_telegram_chat":
        username = action_in.get("username", "")
        return f"✈️ Opened Telegram conversation with **@{username}**."

    elif action == "launch_installed_app":
        app = action_in.get("app_name", "")
        return f"🚀 Launched application **{app}** on device."

    elif action == "torch":
        state = "ON 💡" if action_in.get("enabled", True) else "OFF 🌑"
        return f"🔦 Flashlight turned **{state}**."

    elif action == "list_recent_media":
        return f"📁 Queried your local media vault:\n{obs}"

    elif action == "record_audio_start":
        return f"🎙️ Started audio recording in your media vault: {obs}"

    elif action == "record_audio_stop":
        return f"⏹️ Stopped audio recording. Audio file saved and mirrored to vault!"

    # Fallback summary
    if obs and len(obs) < 300:
        return f"✨ Executed `{action}` successfully:\n{obs}"
    elif obs:
        return f"✨ Completed `{action}`! Result:\n```\n{obs[:250]}...\n```"

    return f"✨ Completed request '{query}' across {len(steps)} deliberation step(s)."


# Global singleton agent
global_react_agent = AutonomousReActAgent()

