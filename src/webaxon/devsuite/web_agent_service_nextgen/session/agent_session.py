"""Agent session with runtime state and Debuggable logging.

This module provides AgentSession, which extends the generic SessionBase with
WebAgent-specific runtime state (agent instance, thread, interactive interface)
and a narrowed info type.
"""
import threading
from typing import Optional

from attr import attrs, attrib
from science_modeling_tools.agents.prompt_based_agents.prompt_based_planning_agent import PromptBasedActionPlanningAgent
from science_modeling_tools.ui.queue_interactive import QueueInteractive
from rich_python_utils.service_utils.session_management import SessionBase

from .agent_session_info import AgentSessionInfo


@attrs(slots=False)
class AgentSession(SessionBase):
    """Live agent session with runtime state and Debuggable logging.

    Extends the generic SessionBase with:
    - Narrowed _info type (AgentSessionInfo)
    - agent: The agent instance (created lazily, callable)
    - agent_thread: Thread running the agent (if async mode)
    - interactive: QueueInteractive for agent communication

    Runtime attrs are set after construction via property setters.
    """
    _info: AgentSessionInfo = attrib(kw_only=True)

    # Runtime state (not in constructor — set after creation via properties)
    _agent: Optional[PromptBasedActionPlanningAgent] = attrib(init=False, default=None)
    _agent_thread: Optional[threading.Thread] = attrib(init=False, default=None)
    _interactive: Optional[QueueInteractive] = attrib(init=False, default=None)

    @property
    def info(self) -> AgentSessionInfo:
        """Access the pure data container (narrowed type)."""
        return self._info

    @property
    def agent(self) -> Optional[PromptBasedActionPlanningAgent]:
        return self._agent

    @agent.setter
    def agent(self, value):
        self._agent = value

    @property
    def agent_thread(self) -> Optional[threading.Thread]:
        return self._agent_thread

    @agent_thread.setter
    def agent_thread(self, value):
        self._agent_thread = value

    @property
    def interactive(self) -> Optional[QueueInteractive]:
        return self._interactive

    @interactive.setter
    def interactive(self, value):
        self._interactive = value
