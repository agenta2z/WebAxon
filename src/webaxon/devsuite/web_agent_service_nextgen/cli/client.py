"""Interactive CLI client for web_agent_service_nextgen.

Connects to a running service via file-based queues and provides a REPL for:
- Registering free-text knowledge pieces
- Sending agent requests and receiving responses
"""
import time
from pathlib import Path
from typing import Any, Optional

from rich_python_utils.datetime_utils.common import timestamp
from rich_python_utils.service_utils.queue_service.storage_based_queue_service import StorageBasedQueueService

from agent_foundation.ui.input_modes import InputMode, InputModeConfig

from webaxon.devsuite.common import get_queue_service
from webaxon.devsuite.web_agent_service_nextgen.cli.kb_arg_parser import (
    parse_kb_add, parse_kb_update, parse_kb_del, parse_kb_get, parse_kb_list, parse_kb_restore,
    parse_kb_review_spaces,
)
from webaxon.devsuite.web_agent_service_nextgen.cli.kb_formatters import (
    format_ingestion_result, format_update_results, format_delete_candidates,
    format_delete_results, format_search_results, format_list_results, format_restore_result,
    format_review_spaces_results,
)
from webaxon.devsuite.constants import (
    INPUT_QUEUE_ID,
    RESPONSE_QUEUE_ID,
    CLIENT_CONTROL_QUEUE_ID,
    SERVER_CONTROL_QUEUE_ID,
)


class CLIClient:
    """Interactive REPL client that talks to a running web agent service."""

    def __init__(
        self,
        testcase_root: Path,
        session_id: Optional[str] = None,
        queue_root_path: Optional[Path] = None,
    ):
        self._testcase_root = testcase_root
        self._session_id = session_id or f"cli_{timestamp().replace(' ', '_').replace(':', '')}"
        self._queue_root_path = queue_root_path
        self._queue_service: Optional[StorageBasedQueueService] = None
        self._running = False

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    def connect(self) -> bool:
        """Discover and connect to the running service's queues.

        If ``queue_root_path`` was provided at init, connects directly to that
        path (useful for nextgen service and testing).  Otherwise falls back to
        auto-discovery via ``get_queue_service()``.

        Returns:
            True if connected successfully.
        """
        if self._queue_root_path is not None:
            self._queue_service = StorageBasedQueueService(
                root_path=str(self._queue_root_path)
            )
        else:
            # Try nextgen queue path first (_runtime/queues/), then legacy (_runtime/queue_storage/)
            nextgen_queues_base = self._testcase_root / "_runtime" / "queues"
            if nextgen_queues_base.exists():
                timestamp_dirs = [d for d in nextgen_queues_base.iterdir() if d.is_dir()]
                if timestamp_dirs:
                    latest = max(timestamp_dirs, key=lambda d: d.name)
                    self._queue_service = StorageBasedQueueService(
                        root_path=str(latest)
                    )

            # Fall back to legacy auto-discovery
            if self._queue_service is None:
                qs = get_queue_service(self._testcase_root, log_on_change=True)
                if qs is None:
                    print("Could not find a running service (no queue storage found).")
                    print(f"Looked under: {self._testcase_root}")
                    return False
                self._queue_service = qs

        # Ensure the session-specific input queue exists
        session_input_queue_id = f"{INPUT_QUEUE_ID}_{self._session_id}"
        self._queue_service.create_queue(session_input_queue_id)

        # Ensure control queues exist
        self._queue_service.create_queue(SERVER_CONTROL_QUEUE_ID)
        self._queue_service.create_queue(CLIENT_CONTROL_QUEUE_ID)
        self._queue_service.create_queue(RESPONSE_QUEUE_ID)

        print(f"Connected to service at {self._queue_service.root_path}")
        print(f"Session: {self._session_id}")

        from webaxon.devsuite.config import OPTION_DEFAULT_PROMPT_VERSION, OPTION_BASE_REASONER
        prompt_ver = OPTION_DEFAULT_PROMPT_VERSION if OPTION_DEFAULT_PROMPT_VERSION else '(default)'
        print(f"Prompt version: {prompt_ver}  |  Reasoner: {OPTION_BASE_REASONER}")
        return True

    # ------------------------------------------------------------------
    # Control-message helpers
    # ------------------------------------------------------------------

    def _send_control(self, msg: dict) -> None:
        """Put a message on the server_control queue."""
        self._queue_service.put(SERVER_CONTROL_QUEUE_ID, msg)

    def _wait_for_control_response(
        self, expected_type: str, timeout: float = 10.0
    ) -> Optional[dict]:
        """Poll client_control queue for a response of the given type."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            resp = self._queue_service.get(CLIENT_CONTROL_QUEUE_ID, blocking=False)
            if resp and resp.get("type") == expected_type:
                return resp
            time.sleep(0.2)
        return None

    # ------------------------------------------------------------------
    # Browser profile
    # ------------------------------------------------------------------

    def send_browser_profile(
        self,
        profile_directory: str,
        user_data_dir: Optional[str] = None,
        copy_profile=None,
    ) -> bool:
        """Send the selected Chrome profile to the service.

        Must be called after connect() and before the first agent request
        so the service can configure the WebDriver with the chosen profile.

        Args:
            profile_directory: Profile folder name (e.g. "Default").
            user_data_dir: Chrome user data directory path.
            copy_profile: True to copy to temp dir, a path string to copy
                there, False to disable, or None to leave the service default.

        Returns True if the service acknowledged the profile.
        """
        payload = {
            "profile_directory": profile_directory,
            "user_data_dir": user_data_dir,
        }
        if copy_profile is not None:
            payload["copy_profile"] = copy_profile
        msg = {
            "type": "set_browser_profile",
            "message": payload,
            "timestamp": timestamp(),
        }
        self._send_control(msg)
        resp = self._wait_for_control_response(
            "set_browser_profile_response", timeout=5.0
        )
        if resp and resp.get("success"):
            return True
        return False

    # ------------------------------------------------------------------
    # Knowledge registration
    # ------------------------------------------------------------------

    def register_knowledge(self, content: str) -> None:
        """Send free-text to the service for LLM-based knowledge ingestion.

        The service calls KnowledgeIngestionCLI which uses the LLM to
        structurize the free text into metadata, classified pieces, and graph
        relationships before storing.
        """
        msg = {
            "type": "register_knowledge",
            "message": {
                "content": content,
            },
            "timestamp": timestamp(),
        }
        self._send_control(msg)

        # LLM structuring takes longer than a raw write — use 60s timeout
        resp = self._wait_for_control_response(
            "register_knowledge_response", timeout=60.0
        )
        if resp is None:
            print("[TIMEOUT] No acknowledgment from service (LLM ingestion may still be running).")
        elif resp.get("success"):
            counts = resp.get("counts", {})
            print(f"[OK] Knowledge ingested — {counts}")
        else:
            print(f"[FAIL] {resp.get('message', 'unknown error')}")

    # ------------------------------------------------------------------
    # KB commands
    # ------------------------------------------------------------------

    def kb_add(self, args: str) -> None:
        """Parse free text, send kb_add message, display ingestion counts."""
        try:
            parsed = parse_kb_add(args)
        except ValueError as e:
            print(str(e))
            return

        msg = {
            "type": "kb_add",
            "message": {"text": parsed["text"], "spaces": parsed["spaces"]},
            "timestamp": timestamp(),
        }
        self._send_control(msg)

        resp = self._wait_for_control_response("kb_add_response", timeout=120.0)
        if resp is None:
            print("[TIMEOUT] No response for kb-add (LLM ingestion may still be running).")
        elif resp.get("success"):
            print(f"[OK] {format_ingestion_result(resp['counts'])}")
        else:
            print(f"[FAIL] {resp.get('message', 'unknown error')}")

    def kb_update(self, args: str) -> None:
        """Parse description, send kb_update message, display update results."""
        try:
            parsed = parse_kb_update(args)
        except ValueError as e:
            print(str(e))
            return

        msg = {
            "type": "kb_update",
            "message": {"text": parsed["text"]},
            "timestamp": timestamp(),
        }
        self._send_control(msg)

        resp = self._wait_for_control_response("kb_update_response", timeout=120.0)
        if resp is None:
            print("[TIMEOUT] No response for kb-update (LLM processing may still be running).")
        elif resp.get("success"):
            results = resp.get("results", [])
            if results:
                print(f"[OK] {format_update_results(results)}")
            else:
                print("[OK] No matching knowledge found")
        else:
            print(f"[FAIL] {resp.get('message', 'unknown error')}")

    def kb_del(self, args: str) -> None:
        """Handle two-phase deletion: search → show candidates → confirm → delete.
        Also handles --id direct deletion."""
        try:
            parsed = parse_kb_del(args)
        except ValueError as e:
            print(str(e))
            return

        if parsed["mode"] == "direct":
            msg = {
                "type": "kb_del",
                "message": {
                    "phase": "direct",
                    "piece_id": parsed["piece_id"],
                    "hard": parsed["hard"],
                },
                "timestamp": timestamp(),
            }
            self._send_control(msg)

            resp = self._wait_for_control_response("kb_del_response", timeout=10.0)
            if resp is None:
                print("[TIMEOUT] No response for kb-del.")
            elif resp.get("success"):
                print(f"[OK] {resp.get('message', 'Deleted')}")
            else:
                print(f"[FAIL] {resp.get('message', 'unknown error')}")
            return

        # Query mode: two-phase search + confirm
        query = parsed["query"]
        msg = {
            "type": "kb_del",
            "message": {"phase": "search", "query": query},
            "timestamp": timestamp(),
        }
        self._send_control(msg)

        resp = self._wait_for_control_response("kb_del_response", timeout=10.0)
        if resp is None:
            print("[TIMEOUT] No response for kb-del search.")
            return

        candidates = resp.get("candidates", [])
        if not candidates:
            print("[OK] No matching pieces found")
            return

        print(format_delete_candidates(candidates))
        try:
            choice = input("Enter piece numbers to delete (comma-separated), 'all', or 'cancel': ").strip()
        except EOFError:
            choice = "cancel"

        if choice.lower() == "cancel":
            print("Cancelled")
            return

        if choice.lower() == "all":
            selected_ids = [c["piece_id"] for c in candidates]
        else:
            try:
                indices = [int(x.strip()) for x in choice.split(",")]
                selected_ids = [candidates[i - 1]["piece_id"] for i in indices]
            except (ValueError, IndexError):
                print("[ERROR] Invalid selection")
                return

        confirm_msg = {
            "type": "kb_del",
            "message": {
                "phase": "confirm",
                "query": query,
                "piece_ids": selected_ids,
            },
            "timestamp": timestamp(),
        }
        self._send_control(confirm_msg)

        resp = self._wait_for_control_response("kb_del_response", timeout=10.0)
        if resp is None:
            print("[TIMEOUT] No response for kb-del confirm.")
        elif resp.get("success"):
            print(f"[OK] {format_delete_results(resp.get('results', []))}")
        else:
            print(f"[FAIL] {resp.get('message', 'unknown error')}")

    def kb_get(self, args: str) -> None:
        """Parse query+flags, send kb_get message, display search results."""
        try:
            parsed = parse_kb_get(args)
        except ValueError as e:
            print(str(e))
            return

        msg = {
            "type": "kb_get",
            "message": {
                "query": parsed["query"],
                "domain": parsed["domain"],
                "limit": parsed["limit"],
                "entity_id": parsed["entity_id"],
                "tags": parsed["tags"],
                "spaces": parsed["spaces"],
            },
            "timestamp": timestamp(),
        }
        self._send_control(msg)

        resp = self._wait_for_control_response("kb_get_response", timeout=10.0)
        if resp is None:
            print("[TIMEOUT] No response for kb-get.")
        elif resp.get("success"):
            print(format_search_results(resp.get("results", [])))
        else:
            print(f"[FAIL] {resp.get('message', 'unknown error')}")

    def kb_list(self, args: str) -> None:
        """Parse flags, send kb_list message, display piece list."""
        try:
            parsed = parse_kb_list(args)
        except ValueError as e:
            print(str(e))
            return

        msg = {
            "type": "kb_list",
            "message": {
                "entity_id": parsed["entity_id"],
                "domain": parsed["domain"],
                "spaces": parsed["spaces"],
            },
            "timestamp": timestamp(),
        }
        self._send_control(msg)

        resp = self._wait_for_control_response("kb_list_response", timeout=10.0)
        if resp is None:
            print("[TIMEOUT] No response for kb-list.")
        elif resp.get("success"):
            results = resp.get("results", [])
            if results:
                print(format_list_results(results))
            else:
                print("No knowledge pieces found.")
        else:
            print(f"[FAIL] {resp.get('message', 'unknown error')}")

    def kb_restore(self, args: str) -> None:
        """Parse piece_id, send kb_restore message, display restore result."""
        try:
            parsed = parse_kb_restore(args)
        except ValueError as e:
            print(str(e))
            return

        msg = {
            "type": "kb_restore",
            "message": {"piece_id": parsed["piece_id"]},
            "timestamp": timestamp(),
        }
        self._send_control(msg)

        resp = self._wait_for_control_response("kb_restore_response", timeout=10.0)
        if resp is None:
            print("[TIMEOUT] No response for kb-restore.")
        elif resp.get("success"):
            print(f"[OK] {format_restore_result(resp)}")
        else:
            print(f"[FAIL] {resp.get('message', 'unknown error')}")

    def kb_review_spaces(self, args: str) -> None:
        """Parse flags, send kb_review_spaces message, display results."""
        try:
            parsed = parse_kb_review_spaces(args)
        except ValueError as e:
            print(str(e))
            return

        msg = {
            "type": "kb_review_spaces",
            "message": {
                "mode": parsed["mode"],
                "piece_id": parsed.get("piece_id"),
            },
            "timestamp": timestamp(),
        }
        self._send_control(msg)

        resp = self._wait_for_control_response("kb_review_spaces_response", timeout=10.0)
        if resp is None:
            print("[TIMEOUT] No response for kb-review-spaces.")
        elif resp.get("success"):
            if parsed["mode"] == "list":
                results = resp.get("results", [])
                print(format_review_spaces_results(results))
            else:
                print(f"[OK] {resp.get('message', 'Done')}")
        else:
            print(f"[FAIL] {resp.get('message', 'unknown error')}")

    # ------------------------------------------------------------------
    # Template version
    # ------------------------------------------------------------------

    def set_template_version(self, template_version: str) -> None:
        """Set the template version for this session.

        Must be called before send_agent_request() so the agent is
        created with the correct prompt templates.
        """
        self._send_control({
            "type": "sync_session_template_version",
            "message": {
                "session_id": self._session_id,
                "template_version": template_version,
            },
            "timestamp": timestamp(),
        })
        resp = self._wait_for_control_response(
            "sync_session_template_version_response", timeout=10.0
        )
        if resp and resp.get('error'):
            print(f"[ERROR] Template version change failed: {resp['error']}")
        elif resp:
            print(f"[OK] Template version set to: {resp.get('template_version')}")
        else:
            print("[WARN] No acknowledgment for template version change. Is the service running?")

    # ------------------------------------------------------------------
    # Agent request
    # ------------------------------------------------------------------

    def send_agent_request(self, text: str) -> None:
        """Send user text to the agent and print responses until done."""
        # Sync session so the service knows about us
        self._send_control({
            "type": "sync_session_agent",
            "message": {
                "session_id": self._session_id,
                "agent_type": "DefaultAgent",
            },
            "timestamp": timestamp(),
        })
        # small delay to let the service process the sync
        time.sleep(0.3)

        # Put the user message on the session-specific input queue
        session_input_queue_id = f"{INPUT_QUEUE_ID}_{self._session_id}"
        self._queue_service.put(session_input_queue_id, {
            "user_input": text,
            "session_id": self._session_id,
            "timestamp": timestamp(),
        })
        print("[Sending to agent...]")
        self._poll_responses()

    def _poll_responses(self) -> None:
        """Poll the response queue indefinitely until a final response is received.

        Dispatches on the interaction flag:
        - TurnCompleted / status completed|error: print and stop
        - PendingInput: collect user input and send back to agent
        - Other: print and continue polling
        """
        session_input_queue_id = f"{INPUT_QUEUE_ID}_{self._session_id}"
        while True:
            resp = self._queue_service.get(RESPONSE_QUEUE_ID, blocking=False)
            if resp is None:
                time.sleep(0.5)
                continue

            # Filter for our session
            resp_session = resp.get("session_id", "")
            if resp_session and resp_session != self._session_id:
                # Not ours — put it back
                self._queue_service.put(RESPONSE_QUEUE_ID, resp)
                time.sleep(0.3)
                continue

            flag = resp.get("flag", "")
            if flag == "TurnCompleted" or resp.get("status") in ("completed", "error"):
                self._print_agent_response(resp)
                break
            if flag == "PendingInput":
                self._handle_pending_input(resp, session_input_queue_id)
                continue
            # MessageOnly or other intermediate responses
            self._print_agent_response(resp)

    def _handle_pending_input(self, resp: dict, session_input_queue_id: str) -> None:
        """Handle a PendingInput response: display the agent's question and collect user input.

        If the user types a ``/`` command (e.g. ``/template``, ``/add``),
        the command is processed immediately and the prompt is re-displayed
        so the user can still provide input to the agent.
        """
        response_content = resp.get("response", "")
        if isinstance(response_content, list) and len(response_content) >= 2:
            print(f"[Agent]: {response_content[0]}")
            print(f"[Agent asks]: {response_content[1]}")
        elif isinstance(response_content, list) and len(response_content) == 1:
            print(f"[Agent asks]: {response_content[0]}")
        else:
            print(f"[Agent asks]: {response_content}")

        # Read input_mode from response dict (set by agent via interactive protocol)
        raw_mode = resp.get("input_mode")
        mode_config = InputModeConfig.from_dict(raw_mode) if raw_mode else InputModeConfig()

        # Collect input, intercepting CLI commands
        while True:
            user_answer = self._collect_input(mode_config)
            answer_str = user_answer if isinstance(user_answer, str) else ""

            # Intercept CLI / commands — process them and re-prompt
            if answer_str.startswith("/"):
                if not self._try_handle_command(answer_str):
                    # Unknown command — send to agent as regular input
                    break
                # Known command handled; re-prompt for agent input
                continue
            break

        self._queue_service.put(session_input_queue_id, {
            "user_input": user_answer,
            "session_id": self._session_id,
            "timestamp": timestamp(),
        })
        print("[Response sent to agent...]")

    def _try_handle_command(self, line: str) -> bool:
        """Try to handle a CLI command. Returns True if handled, False if unknown."""
        lower = line.lower()
        if lower.startswith("/template "):
            version = line[10:].strip()
            if version:
                self.set_template_version(version)
            else:
                print("Usage: /template <version>")
            return True
        if lower.startswith("/add "):
            content = line[5:].strip()
            if content:
                self.register_knowledge(content)
            else:
                print("Usage: /add <text>")
            return True
        if lower == "/status":
            self._cmd_status()
            return True
        return False

    # -- Input collection by mode ---------------------------------------------

    def _collect_input(self, mode_config: InputModeConfig) -> Any:
        """Collect user input based on mode. Returns structured data for choice modes, plain string for text modes."""
        mode = mode_config.mode
        if mode == InputMode.PRESS_TO_CONTINUE:
            return self._collect_press_to_continue(mode_config)
        elif mode == InputMode.EXACT_STRING:
            return self._collect_exact_string(mode_config)
        elif mode == InputMode.SINGLE_CHOICE:
            return self._collect_single_choice(mode_config)
        elif mode == InputMode.MULTIPLE_CHOICES:
            return self._collect_multiple_choices(mode_config)
        else:
            return self._collect_free_text(mode_config)

    @staticmethod
    def _collect_free_text(config: InputModeConfig) -> str:
        prompt = config.prompt or "[Your response]: "
        try:
            return input(prompt).strip()
        except EOFError:
            return ""

    @staticmethod
    def _collect_press_to_continue(config: InputModeConfig) -> str:
        prompt = config.prompt or "[Press Enter to continue]"
        try:
            input(prompt)
        except EOFError:
            pass
        return ""

    @staticmethod
    def _collect_exact_string(config: InputModeConfig) -> str:
        """Validate locally for UX (no queue round-trip on retry)."""
        expected = config.expected_string
        prompt = config.prompt or f"[Type '{expected}' to continue]: "
        while True:
            try:
                answer = input(prompt).strip()
            except EOFError:
                answer = ""
            match = (answer == expected) if config.case_sensitive else (answer.lower() == expected.lower())
            if match:
                return expected
            print(f"  Please type '{expected}' to continue.")

    @staticmethod
    def _collect_single_choice(config: InputModeConfig) -> dict:
        """Present options, collect choice. Return structured dict for RichInteractiveBase postprocessing."""
        for i, opt in enumerate(config.options, 1):
            print(f"  {i}) {opt.label}")
        if config.allow_custom:
            print(f"  {len(config.options) + 1}) Other (type your own)")
        prompt = config.prompt or "[Enter choice number]: "
        while True:
            try:
                answer = input(prompt).strip()
            except EOFError:
                answer = "1"
            try:
                idx = int(answer) - 1
                if 0 <= idx < len(config.options):
                    selected_opt = config.options[idx]
                    print(f"  Selected: {selected_opt.label}")
                    if selected_opt.follow_up_prompt:
                        try:
                            follow_up = input(selected_opt.follow_up_prompt).strip()
                        except EOFError:
                            follow_up = ""
                        return {"choice_index": idx, "follow_up_value": follow_up}
                    return {"choice_index": idx}
                elif config.allow_custom and idx == len(config.options):
                    custom = input("  [Your response]: ").strip()
                    return {"custom_text": custom}
            except ValueError:
                pass
            if config.allow_custom and answer:
                return {"custom_text": answer}
            n = len(config.options)
            print(f"  Enter 1-{n}" + (f" or {n + 1} for custom" if config.allow_custom else ""))

    @staticmethod
    def _collect_multiple_choices(config: InputModeConfig) -> dict:
        """Present options, collect multiple choices. Return structured dict for RichInteractiveBase postprocessing."""
        for i, opt in enumerate(config.options, 1):
            print(f"  {i}) {opt.label}")
        if config.allow_custom:
            print(f"  {len(config.options) + 1}) Other (type your own)")
        prompt = config.prompt or "[Enter choice numbers separated by commas, e.g. 1,3]: "
        while True:
            try:
                answer = input(prompt).strip()
            except EOFError:
                answer = "1"
            try:
                indices = [int(x.strip()) - 1 for x in answer.split(',')]
                selections = []
                custom_needed = False
                for idx in indices:
                    if 0 <= idx < len(config.options):
                        selected_opt = config.options[idx]
                        print(f"  Selected: {selected_opt.label}")
                        if selected_opt.follow_up_prompt:
                            try:
                                val = input(selected_opt.follow_up_prompt).strip()
                            except EOFError:
                                val = ""
                            selections.append({"choice_index": idx, "follow_up_value": val})
                        else:
                            selections.append({"choice_index": idx})
                    elif config.allow_custom and idx == len(config.options):
                        custom_needed = True
                    else:
                        raise ValueError
                if custom_needed:
                    custom = input("  [Your response]: ").strip()
                    if custom:
                        selections.append({"custom_text": custom})
                if selections:
                    return {"selections": selections}
            except ValueError:
                pass
            n = len(config.options)
            print(f"  Enter numbers 1-{n} separated by commas" +
                  (f", or {n + 1} for custom" if config.allow_custom else ""))

    @staticmethod
    def _print_agent_response(resp: dict) -> None:
        """Pretty-print an agent response dict."""
        answer = (
            resp.get("answer")
            or resp.get("response")
            or resp.get("message")
            or resp.get("content")
        )
        if isinstance(answer, list):
            for part in answer:
                if part:
                    print(f"[Agent]: {part}")
        elif answer:
            print(f"[Agent]: {answer}")
        else:
            print(f"[Agent response]: {resp}")

    # ------------------------------------------------------------------
    # Meta agent pipeline
    # ------------------------------------------------------------------

    def run_meta_agent(
        self, query: str, run_count: int = 5, debug: bool = False,
    ) -> None:
        """Trigger the meta agent pipeline on the service and poll for results.

        Sends a ``run_meta_agent`` control message, waits for an ack, then
        polls for progress updates until the pipeline completes.

        When *debug* is True, the service runs the pipeline synchronously
        (blocking its control loop) so a debugger can step through each run.
        """
        self._send_control({
            "type": "run_meta_agent",
            "message": {
                "query": query,
                "run_count": run_count,
                "debug": debug,
            },
            "timestamp": timestamp(),
        })

        # Wait for the "started" acknowledgment
        ack = self._wait_for_control_response(
            "run_meta_agent_started", timeout=10.0
        )
        if ack is None:
            print("[TIMEOUT] No acknowledgment from service. Is the service running?")
            return

        total = ack.get("run_count", run_count)
        mode = " (DEBUG - synchronous)" if ack.get("debug") else ""
        print(f"[Meta Agent] Pipeline started with {total} agent runs{mode}...")
        self._poll_meta_agent_responses()

    def _poll_meta_agent_responses(self) -> None:
        """Poll for meta agent progress and completion messages.

        Blocks until a ``run_meta_agent_response`` (completion) message is
        received or 30 minutes elapse.
        """
        deadline = time.time() + 30 * 60  # 30-minute timeout
        while time.time() < deadline:
            resp = self._queue_service.get(CLIENT_CONTROL_QUEUE_ID, blocking=False)
            if resp is None:
                time.sleep(1.0)
                continue

            msg_type = resp.get("type", "")

            if msg_type == "run_meta_agent_agent_output":
                current = resp.get("current_run", "?")
                total = resp.get("total_runs", "?")
                text = resp.get("agent_response", "")
                if text:
                    print(f"[Meta Agent] Run {current}/{total} - Agent: {text}")
                continue

            if msg_type == "run_meta_agent_progress":
                current = resp.get("current_run", "?")
                total = resp.get("total_runs", "?")
                print(f"[Meta Agent] Progress: run {current}/{total}")
                continue

            if msg_type == "run_meta_agent_response":
                success = resp.get("success", False)
                if success:
                    output_path = resp.get("output_path", "")
                    summary = resp.get("summary", "")
                    print(f"[Meta Agent] Completed successfully.")
                    if summary:
                        print(f"  Summary: {summary}")
                    if output_path:
                        print(f"  Results: {output_path}")
                else:
                    error = resp.get("error", "unknown error")
                    print(f"[Meta Agent] Pipeline failed: {error}")
                return

            # Not a meta-agent message — put it back for other consumers
            self._queue_service.put(CLIENT_CONTROL_QUEUE_ID, resp)
            time.sleep(0.5)

        print("[Meta Agent] Timed out waiting for pipeline to complete (30 min).")

    # ------------------------------------------------------------------
    # Meta Debug Commands
    # ------------------------------------------------------------------

    def _handle_meta_debug_command(self, rest: str) -> None:
        """Parse and dispatch /meta-debug subcommands."""
        parts = rest.split(maxsplit=1)
        subcommand = parts[0].lower() if parts else ""
        args = parts[1].strip() if len(parts) > 1 else ""

        if subcommand == "collect":
            query, run_count = self._parse_collect_args(args)
            if not query:
                print("Usage: /meta-debug collect <query> [--runs N]")
                return
            self._run_debug_collect(query, run_count)

        elif subcommand in ("evaluate", "synthesize", "validate"):
            session_id = args
            if not session_id:
                print(f"Usage: /meta-debug {subcommand} <session_id>")
                return
            self._run_debug_advance(subcommand, session_id)

        elif subcommand == "status":
            self._run_debug_status(args or None)

        elif subcommand == "abort":
            if not args:
                print("Usage: /meta-debug abort <session_id>")
                return
            self._run_debug_abort(args)

        else:
            print("Usage: /meta-debug <collect|evaluate|synthesize|validate|status|abort> ...")
            print("  Hint: Use '/meta-debug collect <query>' to start a new debug session.")

    @staticmethod
    def _parse_collect_args(args: str) -> tuple:
        """Parse: <query> [--runs N]. Returns (query, run_count).

        ``--runs`` is only recognized at the END of the string to avoid
        collision with query text that happens to contain '--runs'.
        """
        run_count = 5
        parts = args.split()
        if len(parts) >= 2 and parts[-2] == "--runs":
            try:
                run_count = int(parts[-1])
                parts = parts[:-2]
            except ValueError:
                print(f"[Meta Debug] Warning: invalid --runs value '{parts[-1]}', using default {run_count}")
        return " ".join(parts), run_count

    def _run_debug_collect(self, query: str, run_count: int) -> None:
        """Send collect command and poll for stage completion."""
        self._send_control({
            "type": "meta_debug_command",
            "message": {"command": "collect", "query": query, "run_count": run_count},
            "timestamp": timestamp(),
        })
        print("[Meta Debug] Starting collect...")
        self._poll_debug_stage_responses(session_id=None)

    def _run_debug_advance(self, subcommand: str, session_id: str) -> None:
        """Send advance command and poll for stage completion."""
        self._send_control({
            "type": "meta_debug_command",
            "message": {"command": subcommand, "session_id": session_id},
            "timestamp": timestamp(),
        })
        print(f"[Meta Debug] Running {subcommand.upper()} for session {session_id}...")
        self._poll_debug_stage_responses(session_id)

    def _run_debug_status(self, session_id: Optional[str]) -> None:
        """Send status command and display result."""
        msg = {"command": "status"}
        if session_id:
            msg["session_id"] = session_id
        self._send_control({
            "type": "meta_debug_command",
            "message": msg,
            "timestamp": timestamp(),
        })
        # Wait for status response
        deadline = time.time() + 10
        while time.time() < deadline:
            resp = self._queue_service.get(CLIENT_CONTROL_QUEUE_ID, blocking=False)
            if resp is None or not isinstance(resp, dict):
                time.sleep(0.5)
                continue

            msg_type = resp.get("type", "")
            if msg_type == "meta_debug_status":
                if "sessions" in resp:
                    sessions = resp["sessions"]
                    if not sessions:
                        print("[Meta Debug] No active debug sessions.")
                    else:
                        print(f"[Meta Debug] Active sessions ({len(sessions)}):")
                        for s in sessions:
                            state = s.get("completed_state", "starting")
                            next_cmd = s.get("next_command", "?")
                            print(f"  {s['session_id']}  state={state}  next={next_cmd}  query={s.get('query', '')}")
                else:
                    sid = resp.get("session_id", "?")
                    state = resp.get("completed_state", "starting")
                    next_cmd = resp.get("next_command")
                    done = resp.get("pipeline_done", False)
                    print(f"[Meta Debug] Session {sid}")
                    print(f"  State: {state}")
                    if next_cmd:
                        print(f"  Next: /meta-debug {next_cmd} {sid}")
                    if done:
                        print(f"  Pipeline: finished")
                return

            if msg_type == "meta_debug_error":
                print(f"[Meta Debug] Error: {resp.get('error', 'unknown')}")
                return

            self._queue_service.put(CLIENT_CONTROL_QUEUE_ID, resp)
            time.sleep(0.5)

        print("[Meta Debug] Timeout waiting for status.")

    def _run_debug_abort(self, session_id: str) -> None:
        """Send abort command."""
        self._send_control({
            "type": "meta_debug_command",
            "message": {"command": "abort", "session_id": session_id},
            "timestamp": timestamp(),
        })
        print(f"[Meta Debug] Session {session_id} abort requested.")

    def _poll_debug_stage_responses(self, session_id: Optional[str]) -> None:
        """Poll for debug stage messages until a stage completes or pipeline finishes."""
        deadline = time.time() + 30 * 60
        while time.time() < deadline:
            resp = self._queue_service.get(CLIENT_CONTROL_QUEUE_ID, blocking=False)
            if resp is None or not isinstance(resp, dict):
                time.sleep(0.5)
                continue

            msg_type = resp.get("type", "")

            if msg_type == "meta_debug_session_created":
                session_id = resp.get("session_id", "?")
                print(f"[Meta Debug] Session {session_id} created. Running COLLECT...")
                continue

            if msg_type == "run_meta_agent_agent_output":
                text = resp.get("agent_response", "")
                if text:
                    current = resp.get("current_run", "?")
                    total = resp.get("total_runs", "?")
                    print(f"  [Agent] Run {current}/{total}: {text}")
                continue

            if msg_type == "run_meta_agent_progress":
                current = resp.get("current_run", "?")
                total = resp.get("total_runs", "?")
                print(f"  [Progress] Run {current}/{total} completed")
                continue

            if msg_type == "run_meta_agent_debug_state":
                self._display_stage_result(resp)
                # For VALIDATE (last stage), keep polling for the final response.
                # Ordering is guaranteed: both debug_state and run_meta_agent_response
                # are enqueued from the same pipeline thread sequentially (FIFO queue).
                if resp.get("state") == "VALIDATE":
                    continue
                return

            if msg_type == "run_meta_agent_response":
                self._display_final_result(resp)
                return

            if msg_type == "meta_debug_error":
                print(f"[Meta Debug] Error: {resp.get('error', 'unknown')}")
                return

            # Put back unrecognized messages
            self._queue_service.put(CLIENT_CONTROL_QUEUE_ID, resp)
            time.sleep(0.5)

        print("[Meta Debug] Timeout waiting for stage completion.")

    @staticmethod
    def _display_stage_result(resp: dict) -> None:
        """Display a stage completion message."""
        state = resp.get("state", "?")
        session_id = resp.get("session_id", "?")
        summary = resp.get("summary", {})
        next_cmd = resp.get("next_command")
        checkpoint = resp.get("checkpoint_path", "")

        print(f"\n{'=' * 60}")
        print(f"[Meta Debug] {state} completed — session {session_id}")
        print(f"{'=' * 60}")

        if state == "COLLECT":
            print(f"  Traces collected: {summary.get('trace_count', '?')}")
        elif state == "EVALUATE":
            print(f"  Passed: {summary.get('passed_count', '?')}/{summary.get('total_count', '?')}")
        elif state == "SYNTHESIZE":
            print(f"  Graph: {'yes' if summary.get('has_graph') else 'no'}")
            report = summary.get("synthesis_report", {})
            if report:
                print(f"  Report: {report}")
        elif state == "VALIDATE":
            if summary.get("skipped"):
                print("  Validation: skipped (config.validate=False)")
            else:
                print(f"  All passed: {summary.get('all_passed', '?')}")
                rate = summary.get("success_rate")
                if rate is not None:
                    print(f"  Success rate: {rate:.1%}")

        if checkpoint:
            print(f"  Checkpoint: {checkpoint}")
        if next_cmd:
            print(f"\n  Next: /meta-debug {next_cmd} {session_id}")

    @staticmethod
    def _display_final_result(resp: dict) -> None:
        """Display the final pipeline result."""
        success = resp.get("success", False)
        if success:
            output_path = resp.get("output_path", "")
            summary = resp.get("summary", "")
            print("[Meta Agent] Completed successfully.")
            if summary:
                print(f"  Summary: {summary}")
            if output_path:
                print(f"  Results: {output_path}")
        else:
            error = resp.get("error", "unknown error")
            print(f"[Meta Agent] Pipeline failed: {error}")

    # ------------------------------------------------------------------
    # REPL
    # ------------------------------------------------------------------

    def run(
        self,
        profile_directory: Optional[str] = None,
        user_data_dir: Optional[str] = None,
        copy_profile=None,
    ) -> None:
        """Run the interactive REPL loop.

        Args:
            profile_directory: Chrome profile folder name to send to the
                service (e.g. "Default", "Profile 1").  Skipped when None.
            user_data_dir: Chrome user data directory path.  Skipped when None.
            copy_profile: True to copy profile to temp dir, a path string to
                copy there for reuse, False to disable, or None for service default.
        """
        if not self.connect():
            return

        if profile_directory:
            ok = self.send_browser_profile(profile_directory, user_data_dir, copy_profile)
            if not ok:
                print("Warning: service did not acknowledge browser profile. Continuing anyway.")

        self._running = True
        print()
        print("Commands:")
        print("  /add <text>        Ingest free-text knowledge via LLM structuring")
        print("  /template <ver>    Set prompt template version (e.g. end_customers)")
        print("  /meta <query>      Run meta agent pipeline (trace collection + synthesis)")
        print("  /meta-debug <cmd>  Stage-by-stage debug (collect|evaluate|synthesize|validate|status|abort)")
        print("  /kb-add <text>       Ingest knowledge via LLM structuring")
        print("  /kb-update <text>    Update knowledge via semantic search + LLM")
        print("  /kb-del <query>      Delete knowledge (semantic search + confirm)")
        print("  /kb-get <query>      Search knowledge base")
        print("  /kb-list             List knowledge pieces")
        print("  /kb-restore <id>     Restore a soft-deleted piece")
        print("  /kb-review-spaces    Review pending space suggestions")
        print("  /status            Show connection and session status")
        print("  /quit              Exit")
        print()
        print("Default: text is sent as an agent request.")
        print()

        try:
            while self._running:
                try:
                    line = input("> ").strip()
                except EOFError:
                    break

                if not line:
                    continue

                if line.lower() in ("/quit", "/exit", "/q"):
                    break
                elif line.lower() == "/status":
                    self._cmd_status()
                elif line.lower().startswith("/add "):
                    content = line[5:].strip()
                    if content:
                        self.register_knowledge(content)
                    else:
                        print("Usage: /add <text>")
                elif line.lower().startswith("/template "):
                    version = line[10:].strip()
                    if version:
                        self.set_template_version(version)
                    else:
                        print("Usage: /template <version>")
                elif line.lower().startswith("/meta-debug"):
                    rest = line[11:].strip()
                    if rest:
                        try:
                            self._handle_meta_debug_command(rest)
                        except KeyboardInterrupt:
                            print("\n[Interrupted] Stopped waiting for meta debug stage.")
                    else:
                        print("Usage: /meta-debug <collect|evaluate|synthesize|validate|status|abort> ...")
                elif line.lower().startswith("/meta "):
                    query = line[6:].strip()
                    if query:
                        try:
                            self.run_meta_agent(query)
                        except KeyboardInterrupt:
                            print("\n[Interrupted] Stopped waiting for meta agent pipeline.")
                    else:
                        print("Usage: /meta <task description>")
                elif line.lower().startswith("/kb-add "):
                    self.kb_add(line[8:])
                elif line.lower().startswith("/kb-update "):
                    self.kb_update(line[11:])
                elif line.lower().startswith("/kb-del "):
                    self.kb_del(line[8:])
                elif line.lower().startswith("/kb-get "):
                    self.kb_get(line[8:])
                elif line.lower().startswith("/kb-list"):
                    self.kb_list(line[8:])
                elif line.lower().startswith("/kb-restore "):
                    self.kb_restore(line[12:])
                elif line.lower().startswith("/kb-review-spaces"):
                    self.kb_review_spaces(line[17:])
                else:
                    try:
                        self.send_agent_request(line)
                    except KeyboardInterrupt:
                        print("\n[Interrupted] Stopped waiting for agent response.")

        except KeyboardInterrupt:
            print("\nInterrupted.")

        print("Goodbye.")

    def _cmd_status(self) -> None:
        """Print status information."""
        from webaxon.devsuite.config import OPTION_DEFAULT_PROMPT_VERSION, OPTION_BASE_REASONER
        prompt_ver = OPTION_DEFAULT_PROMPT_VERSION if OPTION_DEFAULT_PROMPT_VERSION else '(default)'
        print(f"  Session ID      : {self._session_id}")
        print(f"  Queue root      : {self._queue_service.root_path if self._queue_service else 'N/A'}")
        print(f"  Testcase        : {self._testcase_root}")
        print(f"  Prompt version  : {prompt_ver}")
        print(f"  Reasoner        : {OPTION_BASE_REASONER}")
