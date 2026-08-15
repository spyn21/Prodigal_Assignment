from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict

from src.parser import parse_message


class InputInterpreter(ABC):
    """Interpret raw user text into candidate structured fields.

    Implementations may be deterministic or LLM-backed, but user text remains
    untrusted candidate data. Authorization remains in the deterministic state
    machine and verification/business logic.
    """

    @abstractmethod
    def interpret(self, user_input: str) -> Dict[str, Any]:
        raise NotImplementedError


class DeterministicInterpreter(InputInterpreter):
    """Default/fallback parser used for offline, deterministic extraction."""

    def interpret(self, user_input: str) -> Dict[str, Any]:
        return parse_message(user_input or "")


class LLMInterpreter(InputInterpreter):
    """Optional LLM-backed extractor. It must never be the authority for payments."""

    def __init__(self, extractor=None):
        self.extractor = extractor

    def interpret(self, user_input: str) -> Dict[str, Any]:
        if self.extractor is None:
            return DeterministicInterpreter().interpret(user_input)

        raw = self.extractor(user_input or "")
        if not isinstance(raw, dict):
            return DeterministicInterpreter().interpret(user_input)

        # Conservative fallback: the parser remains authoritative in the absence of
        # a valid structured payload from the LLM extractor.
        deterministic = DeterministicInterpreter().interpret(user_input)
        deterministic.update({k: v for k, v in raw.items() if v is not None})
        return deterministic


__all__ = ["InputInterpreter", "DeterministicInterpreter", "LLMInterpreter"]
