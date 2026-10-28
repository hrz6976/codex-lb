from __future__ import annotations

from datetime import timedelta

import pytest
from alembic import command
from sqlalchemy import create_engine, inspect, text

from app.core.config.settings_cache import get_settings_cache
from app.core.crypto import TokenEncryptor
from app.core.usage.pool_notifications import PoolQuotaState, read_pool_quota_state
from app.core.utils.time import naive_utc_to_epoch, utcnow
from app.db.migrate import _build_alembic_config, run_upgrade
from app.db.models import Account, AccountStatus, DashboardSettings, UsageHistory
from app.db.session import SessionLocal

pytestmark = pytest.mark.integration
PATH = "/api/settings/notifications"


@pytest.mark.asyncio
async def test_bark_configuration_is_encrypted_and_can_be_disabled(async_client):
    assert (await async_client.get(PATH)).json() == {"configured": False}
    secret = "https://bark.example/private-device-key"
    response = await async_client.put(PATH, json={"barkUrl": secret})
    assert response.status_code == 200
    assert response.json() == {"configured": True}
    assert secret not in (await async_client.get("/api/settings")).text
    async with SessionLocal() as session:
        row = await session.get(DashboardSettings, 1)
        assert row.bark_url_encrypted != secret.encode()
        assert TokenEncryptor().decrypt(row.bark_url_encrypted) == secret
    assert (await get_settings_cache().get()).bark_url_encrypted is not None
    assert (await async_client.put(PATH, json={"barkUrl": None})).json() == {"configured": False}
    assert (await get_settings_cache().get()).bark_url_encrypted is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url",
    [
        "",
        "https://bark.example",
        "file:///secret",
        "https://u:p@bark.example/key",
        "https://bark.example/key?x=y",
        "https://bark.example/key#frag",
        "https://bark.example:invalid/key",
        "https://bark.example/key with spaces",
    ],
)
async def test_bark_rejects_invalid_destinations(async_client, url):
    response = await async_client.put(PATH, json={"barkUrl": url})
    assert response.status_code == 422
    assert (await async_client.get(PATH)).json() == {"configured": False}


@pytest.mark.asyncio
async def test_bark_settings_require_security_permission(async_client, app_instance, monkeypatch):
    from app.core.auth.dashboard_access import Permission
    from tests.integration.test_dashboard_permission_gates import _principal_without, _use_principal

    _use_principal(app_instance, monkeypatch, _principal_without(Permission.SECURITY_WRITE))
    assert (await async_client.get(PATH)).status_code == 403
    assert (await async_client.put(PATH, json={"barkUrl": "https://bark.example/key"})).status_code == 403


@pytest.mark.asyncio
async def test_pool_observation_excludes_disabled_accounts_and_requires_all_enabled(async_client):
    assert await read_pool_quota_state() == (PoolQuotaState.UNKNOWN, 0)
    now = utcnow()
    async with SessionLocal() as session:
        for name, status in [
            ("one", AccountStatus.ACTIVE),
            ("two", AccountStatus.QUOTA_EXCEEDED),
            ("paused", AccountStatus.PAUSED),
            ("reauth", AccountStatus.REAUTH_REQUIRED),
            ("deactivated", AccountStatus.DEACTIVATED),
            ("deleting", AccountStatus.ACTIVE),
        ]:
            session.add(
                Account(
                    id=name,
                    email=f"{name}@example.com",
                    plan_type="plus",
                    status=status,
                    access_token_encrypted=b"a",
                    refresh_token_encrypted=b"r",
                    id_token_encrypted=b"i",
                    last_refresh=now,
                    delete_requested_at=now if name == "deleting" else None,
                )
            )
        await session.commit()
        session.add(
            UsageHistory(
                account_id="one",
                window="secondary",
                used_percent=100,
                recorded_at=now,
                reset_at=naive_utc_to_epoch(now) + 3600,
                window_minutes=10080,
            )
        )
        await session.commit()
    assert await read_pool_quota_state() == (PoolQuotaState.UNKNOWN, 2)
    async with SessionLocal() as session:
        session.add(
            UsageHistory(
                account_id="two",
                window="secondary",
                used_percent=100,
                recorded_at=now,
                reset_at=naive_utc_to_epoch(now) + 3600,
                window_minutes=10080,
            )
        )
        await session.commit()
    assert await read_pool_quota_state() == (PoolQuotaState.EXHAUSTED, 2)
    async with SessionLocal() as session:
        session.add(
            UsageHistory(
                account_id="two",
                window="secondary",
                used_percent=50,
                recorded_at=now + timedelta(seconds=1),
                reset_at=naive_utc_to_epoch(now) + 3600,
                window_minutes=10080,
            )
        )
        await session.commit()
    # Timestamp remains in the current whole second for deterministic freshness.
    from unittest.mock import patch

    with patch("app.core.usage.pool_notifications.utcnow", return_value=now + timedelta(seconds=1)):
        assert await read_pool_quota_state() == (PoolQuotaState.AVAILABLE, 2)


def test_bark_migration_preserves_existing_settings_and_round_trips(tmp_path):
    url = f"sqlite:///{tmp_path / 'bark.db'}"
    parent = "20260918_000000_merge_scim_and_overflow_heads"
    revision = "20261028_000000_add_bark_notification_secret"
    run_upgrade(url, parent, bootstrap_legacy=False)
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(text("UPDATE dashboard_settings SET sticky_threads_enabled = 0 WHERE id = 1"))
    run_upgrade(url, revision, bootstrap_legacy=False)
    with engine.connect() as connection:
        assert connection.execute(
            text("SELECT sticky_threads_enabled, bark_url_encrypted FROM dashboard_settings")
        ).one() == (0, None)
    command.downgrade(_build_alembic_config(url), parent)
    assert "bark_url_encrypted" not in {c["name"] for c in inspect(engine).get_columns("dashboard_settings")}
    run_upgrade(url, revision, bootstrap_legacy=False)
    with engine.connect() as connection:
        assert connection.execute(
            text("SELECT sticky_threads_enabled, bark_url_encrypted FROM dashboard_settings")
        ).one() == (0, None)
    engine.dispose()
