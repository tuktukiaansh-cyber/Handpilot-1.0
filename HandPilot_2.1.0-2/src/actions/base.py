from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class Action(ABC):
    name: str = "ACTION"

    @abstractmethod
    def execute(self, payload: dict[str, Any] | None = None) -> None:
        """Execute a discrete action once."""

    def update(self, payload: dict[str, Any] | None = None) -> None:
        """Update a continuous action while its gesture remains active."""

    def reset(self) -> None:
        """Reset action state after the gesture deactivates."""
