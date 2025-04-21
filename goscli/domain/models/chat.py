"""Domain models specific to chat interactions.

Includes the `Message` entity and the `ChatSession` aggregate root.
"""

import uuid
import time
from typing import List, Optional
from dataclasses import dataclass, field

# Import common value objects and types
from goscli.domain.models.common import PromptText, ProcessedOutput, TokenCount, MessageRole
from goscli.domain.interfaces.ai_model import ChatMessage

@dataclass
class Message:
    """Entity representing a single message within a chat session."""
    role: MessageRole
    content: PromptText | ProcessedOutput # Can be user input or AI output
    timestamp: float = field(default_factory=time.time)
    token_count: Optional[TokenCount] = None
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_chat_message(self) -> ChatMessage:
        """Converts this domain Message to the ChatMessage format for API calls."""
        # TODO: Implement conversion logic
        return {"role": self.role, "content": str(self.content)}

@dataclass
class ChatSession:
    """Aggregate root representing an ongoing chat conversation."""
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    history: List[Message] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    total_token_count: TokenCount = TokenCount(0)
    # Add other relevant session metadata (e.g., associated user, topic)

    def add_message(self, role: MessageRole, content: PromptText | ProcessedOutput, token_count: Optional[TokenCount] = None) -> None:
        """Adds a new message to the session history and updates token count."""
        # TODO: Implement message adding logic, including token count update
        new_message = Message(role=role, content=content, token_count=token_count)
        self.history.append(new_message)
        if token_count is not None:
            self.total_token_count = TokenCount(self.total_token_count + token_count)

    def get_history(self) -> List[Message]:
        """Returns the full message history."""
        # TODO: Maybe add filtering or slicing options?
        return self.history

    def get_history_for_api(self) -> List[ChatMessage]:
        """Returns the message history formatted for API calls (List[ChatMessage])."""
        # TODO: Implement conversion for the entire history
        return [msg.to_chat_message() for msg in self.history]

    def update_history(self, new_history: List[Message]) -> None:
        """Replaces the current history, e.g., after optimization."""
        # TODO: Implement history replacement and token recalculation
        self.history = new_history
        self.total_token_count = TokenCount(sum(m.token_count or 0 for m in new_history if m.token_count is not None))

    # TODO: Add methods for summarization, session management, etc.

    # --- Deprecated Methods (kept for reference, remove later) ---
    # def get_history_tuples(self) -> List[Tuple[str, str]]:
    #     """DEPRECATED: Returns history as simple tuples."""
    #     return [(msg.role, msg.content) for msg in self.history]

    # def get_full_context(self) -> str:
    #     """DEPRECATED: Returns history as a single formatted string."""
    #     return "\n".join([f"{msg.role.capitalize()}: {msg.content}" for msg in self.history])

    # TODO: Add methods for summarization
    # def summarize_history(self, target_token_limit: int) -> None:
    #     pass 