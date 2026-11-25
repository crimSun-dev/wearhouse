"""Outbox dispatch with per-consumer idempotent delivery records.

Events are written inside business transactions (rolled back with them). The dispatcher runs
outside those transactions, never makes network calls while holding business locks, and records
(consumer, event_id) after a consumer succeeds, so a repeated dispatch never re-delivers.
Consumers must also be idempotent by event id: a crash between the consumer effect and the
delivery record can repeat a call (at-least-once).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Callable

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Engine

from .clock import Clock, utcnow
from .tables import outbox_delivery, outbox_event

log = logging.getLogger("wearhouse.outbox")


@dataclass(frozen=True)
class OutboxMessage:
    id: object
    event_type: str
    aggregate_type: str
    aggregate_id: object
    payload: dict


Consumer = Callable[[OutboxMessage], None]


class OutboxDispatcher:
    def __init__(self, engine: Engine, consumers: dict[str, Consumer], *, clock: Clock = utcnow,
                 batch_size: int = 50, max_backoff_s: int = 3600):
        self.engine = engine
        self.consumers = consumers
        self.clock = clock
        self.batch_size = batch_size
        self.max_backoff_s = max_backoff_s

    def dispatch_once(self) -> dict[str, int]:
        stats = {"delivered": 0, "failed": 0, "events": 0}
        now = self.clock()
        with self.engine.begin() as conn:
            rows = conn.execute(
                select(outbox_event).where(outbox_event.c.dispatched_at.is_(None),
                                           outbox_event.c.available_at <= now)
                .order_by(outbox_event.c.created_at, outbox_event.c.id)
                .limit(self.batch_size).with_for_update(skip_locked=True)).all()
            for row in rows:
                stats["events"] += 1
                msg = OutboxMessage(row.id, row.event_type, row.aggregate_type, row.aggregate_id, row.payload)
                done = set(conn.execute(select(outbox_delivery.c.consumer)
                                        .where(outbox_delivery.c.event_id == row.id)).scalars())
                failed = None
                for name, consumer in sorted(self.consumers.items()):
                    if name in done:
                        continue
                    try:
                        consumer(msg)
                    except Exception as exc:  # noqa: BLE001 - recorded, retried later
                        failed = f"{name}: {type(exc).__name__}"
                        stats["failed"] += 1
                        break
                    conn.execute(pg_insert(outbox_delivery).values(consumer=name, event_id=row.id, delivered_at=now)
                                 .on_conflict_do_nothing())
                    stats["delivered"] += 1
                if failed:
                    backoff = min(self.max_backoff_s, 2 ** min(row.attempts, 12))
                    conn.execute(update(outbox_event).where(outbox_event.c.id == row.id)
                                 .values(attempts=row.attempts + 1, last_error=failed,
                                         available_at=now + timedelta(seconds=backoff)))
                    log.warning("outbox event %s retry scheduled (%s)", row.id, failed)
                else:
                    conn.execute(update(outbox_event).where(outbox_event.c.id == row.id)
                                 .values(dispatched_at=now, attempts=row.attempts + 1, last_error=None))
        return stats


def log_consumer(msg: OutboxMessage) -> None:
    """Default consumer: structured, secret-free event log (payloads never contain secrets)."""
    log.info("event %s %s %s", msg.event_type, msg.aggregate_type, msg.aggregate_id)
