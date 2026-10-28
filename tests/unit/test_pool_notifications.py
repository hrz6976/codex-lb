from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import httpx
import pytest
from pydantic import SecretStr

from app.core.usage import pool_notifications as notifications
from app.core.usage import refresh_scheduler as scheduler_module
from app.core.usage.pool_notifications import BarkPoolNotifier, PoolQuotaState, account_quota_state
from app.db.models import Account, AccountStatus, DashboardSettings, UsageHistory

pytestmark = pytest.mark.unit
NOW = 1_800_000_000


def usage(window: str = "secondary", used: float = 100, **overrides) -> UsageHistory:
    values = {
        "account_id": "one",
        "window": window,
        "used_percent": used,
        "reset_at": NOW + 3600,
        "recorded_at": datetime.fromtimestamp(NOW, timezone.utc).replace(tzinfo=None),
        "window_minutes": 300 if window == "primary" else 10080,
    }
    return UsageHistory(**(values | overrides))


@pytest.mark.parametrize(
    "primary,secondary,monthly,plan,expected",
    [
        (None, usage(), None, "plus", PoolQuotaState.EXHAUSTED),
        (usage("primary"), usage(used=20), None, "plus", PoolQuotaState.EXHAUSTED),
        (None, usage(used=20), None, "plus", PoolQuotaState.AVAILABLE),
        (None, None, None, "plus", PoolQuotaState.UNKNOWN),
        (None, usage(reset_at=NOW), None, "plus", PoolQuotaState.UNKNOWN),
        (
            None,
            usage(recorded_at=datetime.fromtimestamp(NOW - 1000, timezone.utc).replace(tzinfo=None)),
            None,
            "plus",
            PoolQuotaState.UNKNOWN,
        ),
        (None, usage(credits_balance=1), None, "plus", PoolQuotaState.AVAILABLE),
        (None, usage(credits_unlimited=True), None, "plus", PoolQuotaState.AVAILABLE),
        (None, usage(credits_has=True, credits_balance=0), None, "plus", PoolQuotaState.EXHAUSTED),
        (usage("primary"), usage(credits_balance=1), None, "plus", PoolQuotaState.EXHAUSTED),
        (usage("primary", window_minutes=10080, credits_balance=1), None, None, "free", PoolQuotaState.AVAILABLE),
        (None, None, usage("monthly", window_minutes=43200), "free", PoolQuotaState.EXHAUSTED),
        (None, None, usage("monthly", window_minutes=43200), "plus", PoolQuotaState.UNKNOWN),
        (usage("primary", used=0, reset_at=None, window_minutes=None), usage(), None, "plus", PoolQuotaState.EXHAUSTED),
        (usage("primary", used=0, reset_at=NOW - 1), usage(used=20), None, "plus", PoolQuotaState.UNKNOWN),
    ],
)
def test_quota_evidence(primary, secondary, monthly, plan, expected):
    assert account_quota_state(Account(id="one", plan_type=plan), primary, secondary, monthly, now=NOW) == expected


@pytest.mark.asyncio
async def test_delivery_retry_suppression_recovery_and_disable(monkeypatch, caplog):
    from app.core.crypto import TokenEncryptor

    secret = "https://bark.example/device-secret"
    snapshot = DashboardSettings(bark_url_encrypted=TokenEncryptor().encrypt(secret))
    cache = AsyncMock()
    cache.get.return_value = snapshot
    monkeypatch.setattr(notifications, "get_settings_cache", lambda: cache)
    state = AsyncMock(return_value=(PoolQuotaState.EXHAUSTED, 2))
    monkeypatch.setattr(notifications, "read_pool_quota_state", state)
    requests = []
    replies = [500, 200, 200]

    def handle(request):
        requests.append(request)
        return httpx.Response(replies.pop(0), json={"code": 200})

    original = httpx.AsyncClient
    monkeypatch.setattr(
        notifications.httpx, "AsyncClient", lambda **kwargs: original(**kwargs, transport=httpx.MockTransport(handle))
    )
    notifier = BarkPoolNotifier()
    await notifier.check()  # Failure remains retryable.
    await notifier.check()
    await notifier.check()  # Successful delivery suppresses duplicates.
    assert len(requests) == 2
    state.return_value = (PoolQuotaState.UNKNOWN, 0)
    await notifier.check()
    state.return_value = (PoolQuotaState.EXHAUSTED, 2)
    await notifier.check()
    assert len(requests) == 2
    state.return_value = (PoolQuotaState.AVAILABLE, 2)
    await notifier.check()
    state.return_value = (PoolQuotaState.EXHAUSTED, 2)
    await notifier.check()
    assert len(requests) == 3
    assert str(requests[0].url) == "https://bark.example/push"
    assert json.loads(requests[0].content)["device_key"] == "device-secret"
    assert "All 2 enabled accounts" in json.loads(requests[0].content)["body"]
    assert "device-secret" not in caplog.text
    snapshot.bark_url_encrypted = None
    state.reset_mock()
    await notifier.check()
    state.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("response", [httpx.Response(200, json={"code": 400}), httpx.Response(200, text="invalid")])
async def test_unsuccessful_bark_response_is_rejected(monkeypatch, response):
    original = httpx.AsyncClient
    monkeypatch.setattr(
        notifications.httpx,
        "AsyncClient",
        lambda **kwargs: original(**kwargs, transport=httpx.MockTransport(lambda request: response)),
    )
    with pytest.raises(ValueError):
        await BarkPoolNotifier()._send(SecretStr("https://bark.example/key"), 1)


@pytest.mark.asyncio
async def test_scheduler_awaits_notification_only_as_leader(monkeypatch):
    @asynccontextmanager
    async def session():
        yield None

    accounts = AsyncMock()
    accounts.list_accounts.return_value = [Account(id="one", plan_type="plus", status=AccountStatus.ACTIVE)]
    monkeypatch.setattr(scheduler_module, "get_background_session", session)
    monkeypatch.setattr(scheduler_module, "AccountsRepository", lambda session: accounts)
    usage_repo = AsyncMock()
    usage_repo.latest_by_account.return_value = {}
    monkeypatch.setattr(scheduler_module, "UsageRepository", lambda session: usage_repo)
    monkeypatch.setattr(scheduler_module, "detach_session_objects", lambda session: None)
    updater = AsyncMock()
    updater.refresh_accounts.return_value = False
    monkeypatch.setattr(scheduler_module, "build_background_usage_updater", lambda: updater)
    monkeypatch.setattr(scheduler_module, "_invalidate_usage_refresh_caches", AsyncMock())
    notifier = AsyncMock()
    scheduler = scheduler_module.UsageRefreshScheduler(60, True, notifier=notifier)
    leader = AsyncMock()

    async def run(callback):
        return await callback()

    leader.run_if_leader.side_effect = run
    monkeypatch.setattr(scheduler_module, "_get_leader_election", lambda: leader)
    await scheduler._refresh_once()
    notifier.check.assert_awaited_once()
    leader.run_if_leader.side_effect = None
    leader.run_if_leader.return_value = None
    await scheduler._refresh_once()
    notifier.check.assert_awaited_once()


@pytest.mark.asyncio
async def test_notification_cancellation_propagates(monkeypatch):
    from app.core.crypto import TokenEncryptor

    cache = AsyncMock()
    cache.get.return_value = DashboardSettings(bark_url_encrypted=TokenEncryptor().encrypt("https://bark.example/key"))
    monkeypatch.setattr(notifications, "get_settings_cache", lambda: cache)
    monkeypatch.setattr(notifications, "read_pool_quota_state", AsyncMock(return_value=(PoolQuotaState.EXHAUSTED, 1)))
    entered = asyncio.Event()
    cleaned = asyncio.Event()

    async def send(self, destination, count):
        try:
            entered.set()
            await asyncio.Future()
        finally:
            cleaned.set()

    monkeypatch.setattr(BarkPoolNotifier, "_send", send)
    notifier = BarkPoolNotifier()
    task = asyncio.create_task(notifier.check())
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert cleaned.is_set()
    assert not notifier._notified


@pytest.mark.asyncio
async def test_timeout_leaves_notification_retryable(monkeypatch):
    from app.core.crypto import TokenEncryptor

    cache = AsyncMock()
    cache.get.return_value = DashboardSettings(bark_url_encrypted=TokenEncryptor().encrypt("https://bark.example/key"))
    monkeypatch.setattr(notifications, "get_settings_cache", lambda: cache)
    monkeypatch.setattr(notifications, "read_pool_quota_state", AsyncMock(return_value=(PoolQuotaState.EXHAUSTED, 1)))
    send = AsyncMock(side_effect=[httpx.ReadTimeout("timeout"), None])
    monkeypatch.setattr(BarkPoolNotifier, "_send", send)
    notifier = BarkPoolNotifier()
    await notifier.check()
    assert not notifier._notified
    await notifier.check()
    assert notifier._notified
    assert send.await_count == 2
