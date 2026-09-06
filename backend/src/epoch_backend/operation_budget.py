"""One host-owned model-request and wall-clock budget across all agents."""

import math
import threading
import time
from collections.abc import Callable


class BudgetExceeded(Exception):
    def __init__(self, code: str, message: str):
        self.code, self.message = code, message
        super().__init__(message)


class OperationBudget:
    def __init__(
        self,
        max_turns: int,
        timeout_seconds: int,
        cancelled: threading.Event,
        on_turn: Callable[[str, int], None],
    ):
        if (
            type(max_turns) is not int
            or type(timeout_seconds) is not int
            or not 1 <= max_turns <= 20
            or not 1 <= timeout_seconds <= 600
        ):
            raise ValueError("Operation limits exceed 20 turns or 600 seconds")
        self.max_turns = max_turns
        self.deadline = time.monotonic() + timeout_seconds
        self.cancelled, self.on_turn = cancelled, on_turn
        self.used = 0
        self._lock = threading.Lock()

    def check(self):
        if self.cancelled.is_set():
            raise BudgetExceeded("cancelled", "Operation was cancelled; partial state is retained.")
        if time.monotonic() >= self.deadline:
            raise BudgetExceeded("time_limit", "The operation's wall-clock limit was reached.")

    def remaining_seconds(self) -> int:
        self.check()
        remaining = math.floor(self.deadline - time.monotonic())
        if remaining < 1:
            raise BudgetExceeded("time_limit", "Insufficient time remains for another request.")
        return remaining

    def remaining_turns(self) -> int:
        self.check()
        return self.max_turns - self.used

    def consume(self, actor: str):
        with self._lock:
            self.check()
            if self.used >= self.max_turns:
                raise BudgetExceeded(
                    "turn_limit", "The shared model-request turn limit was reached."
                )
            self.used += 1
            # Persist authorization before the provider request. If persistence
            # fails the request is vetoed, while its conservative reservation stays.
            self.on_turn(actor, self.used)
