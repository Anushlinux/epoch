"""Host-owned request limits cover both models and concurrent admission."""

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from epoch_backend import operation_budget
from epoch_backend.operation_budget import BudgetExceeded, OperationBudget


@pytest.mark.parametrize(
    "turns,seconds",
    [(0, 600), (21, 600), (20, 0), (20, 601), (True, 600), (1.5, 600), (20, True), (20, 1.5)],
)
def test_only_bounded_integer_limits_are_accepted(turns, seconds):
    with pytest.raises(ValueError):
        OperationBudget(turns, seconds, threading.Event(), lambda *_: None)


def test_debugger_and_executor_share_twenty_total_requests():
    admitted = []
    budget = OperationBudget(20, 600, threading.Event(), lambda *entry: admitted.append(entry))
    for index in range(20):
        budget.consume("debugger" if index % 3 == 0 else "executor")
    assert budget.remaining_turns() == 0
    with pytest.raises(BudgetExceeded) as error:
        budget.consume("executor")
    assert error.value.code == "turn_limit"
    assert len(admitted) == 20
    assert [used for _, used in admitted] == list(range(1, 21))
    assert {actor for actor, _ in admitted} == {"debugger", "executor"}


def test_concurrent_admission_cannot_overspend():
    admitted = []
    budget = OperationBudget(20, 600, threading.Event(), lambda *entry: admitted.append(entry))

    def consume(_):
        try:
            budget.consume("executor")
            return True
        except BudgetExceeded:
            return False

    with ThreadPoolExecutor(max_workers=8) as pool:
        outcomes = list(pool.map(consume, range(50)))
    assert sum(outcomes) == 20
    assert len(admitted) == budget.used == 20


def test_cancellation_denies_admission_without_consuming_a_turn():
    cancelled = threading.Event()
    budget = OperationBudget(20, 600, cancelled, lambda *_: pytest.fail("Admitted after cancel"))
    cancelled.set()
    with pytest.raises(BudgetExceeded) as error:
        budget.consume("debugger")
    assert error.value.code == "cancelled"
    assert budget.used == 0


def test_clock_deadline_is_shared_and_never_refreshed(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr(operation_budget.time, "monotonic", lambda: clock[0])
    budget = OperationBudget(20, 600, threading.Event(), lambda *_: None)
    budget.consume("debugger")
    clock[0] += 400
    budget.consume("executor")
    assert budget.remaining_seconds() == 200
    clock[0] += 200
    with pytest.raises(BudgetExceeded) as error:
        budget.consume("debugger")
    assert error.value.code == "time_limit"
    assert budget.used == 2


def test_failed_authorization_persistence_vetoes_and_keeps_conservative_reservation():
    def cannot_persist(*_):
        raise OSError("Disk is full")

    budget = OperationBudget(20, 600, threading.Event(), cannot_persist)
    with pytest.raises(OSError):
        budget.consume("executor")
    assert budget.used == 1
