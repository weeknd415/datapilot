"""Session-based conversation memory for multi-turn queries."""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class ConversationTurn:
    """A single turn in a conversation."""

    query: str
    answer: str
    timestamp: float = field(default_factory=time.time)


class ConversationMemory:
    """In-memory conversation store keyed by session ID.

    Keeps the last N turns per session and auto-expires
    sessions after a timeout.
    """

    def __init__(
        self,
        max_turns: int = 10,
        session_timeout: int = 3600,
    ):
        self.max_turns = max_turns
        self.session_timeout = session_timeout
        self._sessions: dict[str, list[ConversationTurn]] = defaultdict(
            list
        )

    def add_turn(
        self, session_id: str, query: str, answer: str,
    ) -> None:
        """Add a conversation turn."""
        if not session_id:
            return
        self._cleanup_expired()
        self._sessions[session_id].append(
            ConversationTurn(query=query, answer=answer)
        )
        # Keep only last N turns
        if len(self._sessions[session_id]) > self.max_turns:
            self._sessions[session_id] = self._sessions[session_id][
                -self.max_turns :
            ]

    def get_history(self, session_id: str) -> list[ConversationTurn]:
        """Get conversation history for a session."""
        if not session_id:
            return []
        self._cleanup_expired()
        return self._sessions.get(session_id, [])

    def get_context_string(self, session_id: str) -> str:
        """Get conversation history as a formatted string for LLM."""
        history = self.get_history(session_id)
        if not history:
            return ""

        parts = ["PREVIOUS CONVERSATION:"]
        for turn in history[-5:]:  # Last 5 turns
            parts.append(f"User: {turn.query}")
            parts.append(f"Assistant: {turn.answer[:200]}...")
        return "\n".join(parts)

    def _cleanup_expired(self) -> None:
        """Remove expired sessions."""
        now = time.time()
        expired = []
        for sid, turns in self._sessions.items():
            if turns and (now - turns[-1].timestamp) > self.session_timeout:
                expired.append(sid)
        for sid in expired:
            del self._sessions[sid]


conversation_memory = ConversationMemory()
