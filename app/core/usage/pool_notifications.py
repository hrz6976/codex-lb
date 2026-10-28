from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from enum import Enum
from urllib.parse import unquote

import httpx
from pydantic import SecretStr

from app.core import usage as usage_core
from app.core.config.settings_cache import get_settings_cache
from app.core.crypto import TokenEncryptor
from app.core.usage.quota import apply_usage_quota
from app.core.usage.refresh_policy import usage_freshness_horizon_seconds
from app.core.utils.time import naive_utc_to_epoch, utcnow
from app.db.models import Account, AccountStatus, UsageHistory
from app.db.session import get_background_session
from app.modules.accounts.repository import AccountsRepository
from app.modules.usage.mappers import usage_history_to_window_row
from app.modules.usage.repository import UsageRepository

logger = logging.getLogger(__name__)


class PoolQuotaState(Enum):
    AVAILABLE = "available"
    EXHAUSTED = "exhausted"
    UNKNOWN = "unknown"


def account_quota_state(
    account: Account,
    primary: UsageHistory | None,
    secondary: UsageHistory | None,
    monthly: UsageHistory | None,
    *,
    now: float,
) -> PoolQuotaState:
    """Observe standard quota without changing account health or routing state."""
    if monthly is not None and usage_core.capacity_for_plan(account.plan_type, "monthly") is not None:
        primary, secondary = None, monthly
    elif primary is not None and usage_core.is_weekly_window_minutes(primary.window_minutes):
        if secondary is None or usage_core.should_use_weekly_primary(
            usage_history_to_window_row(primary), usage_history_to_window_row(secondary)
        ):
            secondary = primary
        primary = None

    entries = [entry for entry in (primary, secondary) if entry is not None]

    def fresh(entry: UsageHistory | None) -> bool:
        return (
            entry is not None
            and entry.recorded_at is not None
            and 0 <= now - naive_utc_to_epoch(entry.recorded_at) <= usage_freshness_horizon_seconds()
            and entry.reset_at is not None
            and entry.reset_at > now
            and entry.window_minutes is not None
            and entry.window_minutes > 0
        )

    fresh_entries = [entry for entry in entries if fresh(entry)]
    if not fresh_entries:
        return PoolQuotaState.UNKNOWN
    credit_entries = [
        entry
        for entry in fresh_entries
        if entry.credits_has is not None or entry.credits_unlimited is not None or entry.credits_balance is not None
    ]
    credits = max(credit_entries, key=lambda entry: entry.recorded_at) if credit_entries else None
    status, _, _ = apply_usage_quota(
        status=AccountStatus.ACTIVE,
        primary_used=primary.used_percent if fresh(primary) and primary is not None else None,
        primary_reset=primary.reset_at if primary is not None else None,
        primary_window_minutes=primary.window_minutes if primary is not None else None,
        runtime_reset=None,
        secondary_used=secondary.used_percent if fresh(secondary) and secondary is not None else None,
        secondary_reset=secondary.reset_at if secondary is not None else None,
        credits_has=credits.credits_has if credits is not None else None,
        credits_unlimited=credits.credits_unlimited if credits is not None else None,
        credits_balance=credits.credits_balance if credits is not None else None,
        now=now,
    )
    if status in (AccountStatus.RATE_LIMITED, AccountStatus.QUOTA_EXCEEDED):
        return PoolQuotaState.EXHAUSTED
    # Placeholder slots are absent windows, but stale real windows are unknown.
    if any(entry.window_minutes and entry.window_minutes > 0 and not fresh(entry) for entry in entries):
        return PoolQuotaState.UNKNOWN
    return PoolQuotaState.AVAILABLE


async def read_pool_quota_state() -> tuple[PoolQuotaState, int]:
    async with get_background_session() as session:
        accounts = [
            account
            for account in await AccountsRepository(session).list_accounts()
            if account.status in (AccountStatus.ACTIVE, AccountStatus.RATE_LIMITED, AccountStatus.QUOTA_EXCEEDED)
            and account.delete_requested_at is None
        ]
        if not accounts:
            return PoolQuotaState.UNKNOWN, 0
        ids = [account.id for account in accounts]
        usage = UsageRepository(session)
        primary = await usage.latest_by_account("primary", account_ids=ids)
        secondary = await usage.latest_by_account("secondary", account_ids=ids)
        monthly = await usage.latest_by_account("monthly", account_ids=ids)
        now = naive_utc_to_epoch(utcnow())
        states = [
            account_quota_state(
                account, primary.get(account.id), secondary.get(account.id), monthly.get(account.id), now=now
            )
            for account in accounts
        ]
        if PoolQuotaState.AVAILABLE in states:
            return PoolQuotaState.AVAILABLE, len(accounts)
        if all(state == PoolQuotaState.EXHAUSTED for state in states):
            return PoolQuotaState.EXHAUSTED, len(accounts)
        return PoolQuotaState.UNKNOWN, len(accounts)


@dataclass(slots=True)
class BarkPoolNotifier:
    _destination: bytes | None = None
    _notified: bool = False

    async def check(self) -> None:
        try:
            settings = await get_settings_cache().get()
            destination = settings.bark_url_encrypted
            if destination != self._destination:
                self._destination = destination
                self._notified = False
            if destination is None:
                return
            state, count = await read_pool_quota_state()
            if state == PoolQuotaState.AVAILABLE:
                self._notified = False
            elif state == PoolQuotaState.EXHAUSTED and not self._notified:
                await self._send(SecretStr(TokenEncryptor().decrypt(destination)), count)
                self._notified = True
        except Exception as exc:
            # Do not log exception text/tracebacks: URLs and response bodies may
            # contain the device secret. Cancellation (BaseException) propagates.
            logger.warning("Bark pool notification check failed (%s); will retry", type(exc).__name__)

    async def _send(self, destination: SecretStr, count: int) -> None:
        server, key = destination.get_secret_value().rstrip("/").rsplit("/", 1)
        async with asyncio.timeout(10), httpx.AsyncClient(timeout=10.0, follow_redirects=False) as client:
            response = await client.post(
                f"{server}/push",
                json={
                    "device_key": unquote(key),
                    "title": "Codex LB: all accounts out of credits",
                    "body": (
                        f"All {count} enabled accounts have exhausted their available quota. "
                        "Check the dashboard for reset times or add capacity."
                    ),
                    "group": "codex-lb",
                },
            )
            response.raise_for_status()
            if response.json().get("code") != 200:
                raise ValueError("Bark rejected the notification")
