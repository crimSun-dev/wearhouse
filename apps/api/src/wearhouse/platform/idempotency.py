"""Idempotent mutation execution (actor + route + key, bound to a secret-safe request fingerprint).

Protocol, per request:
  1. Admission transaction: insert-or-lock the record. A completed record replays its stored result
     (no admission hook, so no new attempt). A different fingerprint -> 409 without evaluating the body.
     A live lease held by another request -> wait for it (the effect transaction holds the row lock, so
     waiting usually ends as a replay). New or lease-expired records run the optional `admit` hook
     (e.g. attempt reservation), take a fresh lease token and commit, so that hook's effect persists
     even if the effect transaction later fails.
  2. Effect transaction: re-lock the record, confirm the lease token is still ours, run `execute`, and
     store the outcome in the same transaction as the business effect.
  3. On an exception from `execute`: release the record if nothing durable was reserved, otherwise expire
     its lease so the same key can safely retry (a crashed process is recovered by lease expiry).
A record is never reported successful just because it exists. Only `completed` records replay.
"""
from __future__ import annotations

import json
import re
import time
import uuid
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Callable

from .clock import Clock
from .crypto import PURPOSE_FINGERPRINT, KeyRing
from .errors import ApiError, FieldError, conflict, validation_failed
from .ports import IdempotencyRecord, UnitOfWork

KEY_PATTERN = re.compile(r"^[A-Za-z0-9_.:\-]{8,128}$")
HEADER = "Idempotency-Key"


def require_key(value: str | None) -> str:
    if value is None or not KEY_PATTERN.fullmatch(value):
        raise validation_failed([FieldError(f"header.{HEADER}", "invalid_idempotency_key",
                                            "Send an Idempotency-Key header of 8-128 characters "
                                            "[A-Za-z0-9_.:-].")])
    return value


def canonical(body: Any) -> bytes:
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str).encode()


def fingerprint(ring: KeyRing, route: str, body: Any) -> str:
    """HMAC (not a plain hash) so secret-bearing bodies never yield a digest usable for lookup."""
    return ring.mac(PURPOSE_FINGERPRINT, route.encode() + b"\n" + canonical(body))


def fingerprint_matches(ring: KeyRing, route: str, body: Any, stored: str) -> bool:
    return ring.mac_matches(PURPOSE_FINGERPRINT, route.encode() + b"\n" + canonical(body), stored)


@dataclass(frozen=True)
class Outcome:
    status: int
    body: dict
    replayed: bool


Admit = Callable[[Any, IdempotencyRecord], "ApiError | None"]
Execute = Callable[[Any, IdempotencyRecord], tuple[int, dict]]


class IdempotentExecutor:
    def __init__(self, uow_factory: Callable[[], UnitOfWork], ring: KeyRing, clock: Clock, *,
                 lease_s: float = 15.0, wait_s: float | None = None, poll_s: float = 0.05):
        self.uow_factory = uow_factory
        self.ring = ring
        self.clock = clock
        self.lease = timedelta(seconds=lease_s)
        self.wait_s = lease_s + 2 if wait_s is None else wait_s
        self.poll_s = poll_s

    def run(self, *, actor_id: uuid.UUID, route: str, key: str, body: Any, execute: Execute,
            admit: Admit | None = None) -> Outcome:
        fp = fingerprint(self.ring, route, body)
        deadline = time.monotonic() + self.wait_s
        while True:
            claimed = self._admission(actor_id, route, key, body, fp, admit)
            if isinstance(claimed, Outcome):
                return claimed
            if claimed is None:  # someone else holds a live lease
                if time.monotonic() > deadline:
                    raise ApiError(409, "REQUEST_IN_PROGRESS", "An identical request is still being processed.",
                                   headers={"Retry-After": "1"})
                time.sleep(self.poll_s)
                continue
            record_id, token = claimed
            result = self._effect(record_id, token, execute)
            if result is not None:
                return result
            # lease lost to a takeover: loop back and replay/wait on the winner

    def _admission(self, actor_id, route, key, body, fp, admit):
        now = self.clock()
        with self.uow_factory() as uow:
            rec, created = uow.idempotency.acquire(actor_id=actor_id, route=route, key=key, fingerprint=fp, now=now)
            if not created and not fingerprint_matches(self.ring, route, body, rec.request_fingerprint):
                raise conflict("IDEMPOTENCY_KEY_REUSED",
                               "This Idempotency-Key was already used with a different request body.")
            if rec.status == "completed":
                return Outcome(rec.response_status, rec.response_body or {}, True)
            if not created and rec.lease_expires_at is not None and rec.lease_expires_at > now:
                return None
            if admit is not None:
                err = admit(uow, rec)
                if err is not None:
                    uow.idempotency.release(rec.id)
                    uow.commit()
                    raise err
            token = uuid.uuid4()
            uow.idempotency.start_lease(rec.id, token, now + self.lease)
            uow.commit()
            return rec.id, token

    def _effect(self, record_id, token, execute) -> Outcome | None:
        try:
            with self.uow_factory() as uow:
                rec = uow.idempotency.lock(record_id)
                if rec is None or rec.status != "processing" or rec.lease_token != token:
                    return None
                status, body = execute(uow, rec)
                uow.idempotency.complete(record_id, status, body, self.clock())
                uow.commit()
                return Outcome(status, body, False)
        except BaseException:
            self._abandon(record_id, token)
            raise

    def _abandon(self, record_id, token) -> None:
        try:
            with self.uow_factory() as uow:
                rec = uow.idempotency.lock(record_id)
                if rec is not None and rec.status == "processing" and rec.lease_token == token:
                    uow.idempotency.release(record_id)
                    uow.idempotency.expire_lease(record_id, self.clock())
                    uow.commit()
        except Exception:  # noqa: BLE001 - best effort; lease expiry still recovers the key
            pass
