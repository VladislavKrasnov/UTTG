from __future__ import annotations

import asyncio
from typing import Any

import pytest

from ingestion import scheduler
from providers.transport import ProviderUnavailableError


class FakeValkey:
    def __init__(self) -> None:
        self.expirations: dict[str, int] = {}

    async def set(self, key: str, value: str, ex: int, nx: bool = False) -> bool:
        if nx and key in self.expirations:
            return False
        self.expirations[key] = ex
        return True

    async def ttl(self, key: str) -> int:
        return self.expirations.get(key, -2)


class StopLoop(Exception):
    pass


@pytest.fixture
def recorded(monkeypatch: pytest.MonkeyPatch) -> dict[str, list[Any]]:
    calls: dict[str, list[Any]] = {"health": [], "events": [], "sleeps": []}

    async def health(provider_id: str, status: str, error: str | None = None) -> None:
        calls["health"].append((provider_id, status, error))

    async def publish(event: str, data: dict[str, Any]) -> None:
        calls["events"].append(event)

    monkeypatch.setattr(scheduler, "_provider_health", health)
    monkeypatch.setattr(scheduler, "_publish_event", publish)
    monkeypatch.setattr(scheduler.random, "uniform", lambda low, high: 1.0)
    return calls


async def test_failed_job_backs_off_then_success_holds_full_interval(
    monkeypatch: pytest.MonkeyPatch, recorded: dict[str, list[Any]]
) -> None:
    valkey = FakeValkey()
    attempts = iter([ProviderUnavailableError("down"), None])

    async def job() -> None:
        outcome = next(attempts)
        if outcome:
            raise outcome

    async def fake_sleep(seconds: float) -> None:
        recorded["sleeps"].append(seconds)
        if len(recorded["sleeps"]) == 2:
            raise StopLoop
        valkey.expirations.clear()

    monkeypatch.setattr(scheduler.asyncio, "sleep", fake_sleep)
    with pytest.raises(StopLoop):
        await scheduler._run_guarded(valkey, "celestrak", "orbital", 7200, job)  # type: ignore[arg-type]

    assert recorded["sleeps"] == [60.0, 7200]
    assert recorded["health"][0][:2] == ("celestrak", "error")
    assert "down" in recorded["health"][0][2]
    assert recorded["health"][1][:2] == ("celestrak", "active")
    assert recorded["events"] == ["provider.degraded"]
    assert valkey.expirations["scheduler:lock:orbital"] == 7200


async def test_running_lease_is_short_so_a_crash_retries_soon(
    monkeypatch: pytest.MonkeyPatch, recorded: dict[str, list[Any]]
) -> None:
    valkey = FakeValkey()
    observed: list[int] = []

    async def job() -> None:
        observed.append(valkey.expirations["scheduler:lock:orbital"])
        raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await scheduler._run_guarded(valkey, "celestrak", "orbital", 7200, job)  # type: ignore[arg-type]
    assert observed == [scheduler._RUNNING_LEASE_SECONDS]


def test_retry_delay_grows_and_is_capped_by_interval() -> None:
    delays = [scheduler._retry_delay(failures, 300) for failures in range(1, 6)]
    assert 0.8 * 60 <= delays[0] <= 1.2 * 60
    assert delays[1] > delays[0]
    assert max(delays) <= 300 * 1.2


def test_safe_error_hides_unexpected_exception_text() -> None:
    assert scheduler._safe_error(ValueError("postgresql://user:secret@db")) == "ValueError"
    assert "quota" in scheduler._safe_error(ProviderUnavailableError("quota"))
