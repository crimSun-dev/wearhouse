"""Accounts application service: profiles, privacy, public projections, social graph, lifecycle.

Concurrency (design D6): every operation that touches two accounts locks both `account_profile` rows in
UUID order first, then any request row, so accept/cancel/block/send never deadlock and exactly one
transition wins. Visibility is decided per request by `domain.can_view`; every non-permitted read raises the
same 404 as an unknown or deleted handle.
"""
from __future__ import annotations

import uuid
from datetime import timezone
from typing import Callable

from ..identity.domain import Capability, Principal, parse_roles, require
from ..ownership.application import item_view
from ..platform.clock import Clock, utcnow
from ..platform.crypto import KeyRing
from ..platform.errors import ApiError, FieldError, conflict, not_found, rate_limited, validation_failed
from ..platform.idempotency import IdempotentExecutor, Outcome
from ..platform.pagination import check_limit, decode, decode_sealed, encode, encode_sealed
from ..platform.ports import AttemptScope, FaultHook, no_faults
from . import domain as d
from .ports import AccountsUoW, HandleTaken, ListedAccount, PrivacyRow, ProfileRow

ROUTE_SEND = "POST /api/v2/me/friend-requests"


def _avatar(p: ProfileRow | ListedAccount) -> dict:
    return {"kind": p.avatar_kind, "preset": p.avatar_preset, "url": p.avatar_url}


def card(p: ProfileRow | ListedAccount) -> dict:
    return {"handle": p.handle, "display_name": p.display_name, "avatar": _avatar(p)}


def _privacy(row: PrivacyRow) -> dict:
    return {"profile": row.profile, "wardrobe": row.wardrobe, "friends_list": row.friends_list}


def _not_found() -> ApiError:
    return not_found("Profile not found.")


class AccountsService:
    def __init__(self, uow_factory: Callable[[], AccountsUoW], ring: KeyRing, *, clock: Clock = utcnow,
                 lease_s: float = 15.0, faults: FaultHook = no_faults,
                 export_sections: dict[str, Callable] | None = None, erasers: tuple[Callable, ...] = (),
                 on_onboarded: Callable | None = None):
        self.uow_factory = uow_factory
        self.ring = ring
        self.clock = clock
        self.faults = faults
        # Other modules contribute export sections / deletion steps; wired in bootstrap (dependency inversion).
        self.export_sections = dict(export_sections or {})
        self.erasers = tuple(erasers)
        # Runs inside the transaction that sets an account's first handle (e.g. the starter kit).
        self.on_onboarded = on_onboarded
        self.executor = IdempotentExecutor(uow_factory, ring, clock, lease_s=lease_s)

    # ------------------------------------------------------------------ helpers
    def _own(self, uow: AccountsUoW, principal: Principal) -> ProfileRow:
        """The caller's profile, created on first use (display name seeded from the broker name hint)."""
        p = uow.accounts.get_profile(principal.user_id)
        if p is None:
            p = uow.accounts.ensure_profile(principal.user_id, d.default_display_name(principal.hints.name),
                                            self.clock())
            uow.accounts.ensure_privacy(principal.user_id)
        return p

    def _onboarded(self, uow: AccountsUoW, principal: Principal) -> ProfileRow:
        p = self._own(uow, principal)
        if p.handle is None:
            raise d.handle_required()
        return p

    def _subject(self, uow: AccountsUoW, viewer: Principal | None, handle: str):
        """Resolve a profile for a non-owner read: (profile, privacy, relation) or the uniform 404."""
        try:
            h = d.normalize_handle(handle)
        except ApiError:
            raise _not_found() from None
        owner = uow.accounts.profile_by_handle(h)
        if owner is None:
            raise _not_found()
        privacy = uow.accounts.ensure_privacy(owner.user_id)
        if viewer is None:
            rel = d.relation_of(is_self=False, viewer_known=False, blocked=False, friends=False)
        else:
            r = uow.accounts.relationship(viewer.user_id, owner.user_id)
            rel = d.relation_of(is_self=viewer.user_id == owner.user_id, viewer_known=True, blocked=r.blocked,
                                friends=r.friends)
        if rel is d.Relation.BLOCKED:
            raise _not_found()
        return owner, privacy, rel

    def _target(self, uow: AccountsUoW, me: uuid.UUID, handle: str) -> ProfileRow:
        try:
            h = d.normalize_handle(handle)
        except ApiError:
            raise _not_found() from None
        t = uow.accounts.profile_by_handle(h)
        if t is None:
            raise _not_found()
        if t.user_id == me:
            raise validation_failed([FieldError("body.handle", "self", "You cannot do this to your own account.")])
        return t

    # ------------------------------------------------------------------ me / profile / privacy
    def me(self, principal: Principal) -> dict:
        with self.uow_factory() as uow:
            p = self._own(uow, principal)
            uow.commit()
        return {"user_id": str(principal.user_id), "roles": sorted(r.value for r in principal.roles),
                "capabilities": sorted(c.value for c in principal.capabilities),
                "handle": p.handle, "needs_onboarding": p.handle is None}

    def _profile_view(self, p: ProfileRow, privacy: PrivacyRow) -> dict:
        return {**card(p), "bio": p.bio, "member_since": p.created_at.astimezone(timezone.utc).strftime("%Y-%m"),
                "needs_onboarding": p.handle is None, "privacy": _privacy(privacy)}

    def get_profile(self, principal: Principal) -> dict:
        with self.uow_factory() as uow:
            p = self._own(uow, principal)
            priv = uow.accounts.ensure_privacy(principal.user_id)
            uow.commit()
        return self._profile_view(p, priv)

    def update_profile(self, principal: Principal, patch: dict) -> dict:
        now = self.clock()
        values: dict = {}
        if "display_name" in patch:
            values["display_name"] = d.clean_display_name(patch["display_name"])
        if "bio" in patch:
            values["bio"] = d.clean_bio(patch["bio"])
        if "avatar" in patch:
            av = patch["avatar"]
            if av["kind"] == "preset":
                if av.get("preset") not in d.AVATAR_PRESETS:
                    raise validation_failed([FieldError("body.avatar.preset", "unknown_preset",
                                                        "Choose one of the built-in avatars.")])
                values.update(avatar_kind="preset", avatar_preset=av["preset"], avatar_url=None)
            else:
                if not principal.hints.image:
                    raise validation_failed([FieldError("body.avatar.kind", "no_provider_picture",
                                                        "Your sign-in provider did not supply a picture.")])
                values.update(avatar_kind="provider", avatar_preset=None, avatar_url=principal.hints.image)
        new_handle = d.normalize_handle(patch["handle"]) if patch.get("handle") is not None else None
        with self.uow_factory() as uow:
            self._own(uow, principal)
            current = uow.accounts.lock_profiles(principal.user_id)[principal.user_id]
            old_handle = current.handle
            if new_handle is not None and new_handle != old_handle:
                if d.is_reserved(new_handle):
                    raise d.handle_unavailable()
                hold = uow.accounts.get_hold(new_handle)
                if hold is not None and hold[1] > now and hold[0] != principal.user_id:
                    raise d.handle_unavailable()
                if old_handle is not None and current.handle_changed_at is not None:
                    ready = current.handle_changed_at + d.HANDLE_CHANGE_INTERVAL
                    if ready > now:
                        raise d.handle_change_too_soon((ready - now).total_seconds())
                values["handle"] = new_handle
                if old_handle is not None:
                    values["handle_changed_at"] = now
            try:
                p = uow.accounts.update_profile(principal.user_id, values, now) if values else current
            except HandleTaken:
                raise d.handle_unavailable() from None
            if "handle" in values:
                uow.accounts.delete_hold(new_handle)
                if old_handle is not None:
                    uow.accounts.put_hold(old_handle, principal.user_id, now + d.HANDLE_HOLD)
                    uow.audit.record(actor_id=principal.user_id, action="account.handle_changed", target_type="user",
                                     target_id=str(principal.user_id), details={"handle": new_handle})
            priv = uow.accounts.ensure_privacy(principal.user_id)
            if "handle" in values and old_handle is None and self.on_onboarded is not None:
                self.on_onboarded(uow, principal.user_id, now)
            uow.commit()
        return self._profile_view(p, priv)

    def get_privacy(self, principal: Principal) -> dict:
        with self.uow_factory() as uow:
            self._own(uow, principal)
            row = uow.accounts.ensure_privacy(principal.user_id)
            uow.commit()
        return _privacy(row)

    def set_privacy(self, principal: Principal, settings: dict) -> dict:
        row = PrivacyRow(**{k: d.Visibility(settings[k]).value for k in ("profile", "wardrobe", "friends_list")})
        with self.uow_factory() as uow:
            self._own(uow, principal)
            out = uow.accounts.set_privacy(principal.user_id, row, self.clock())
            uow.audit.record(actor_id=principal.user_id, action="account.privacy_changed", target_type="user",
                             target_id=str(principal.user_id), details=_privacy(out))
            uow.commit()
        return _privacy(out)

    # ------------------------------------------------------------------ public projections
    def public_profile(self, viewer: Principal | None, handle: str) -> dict:
        with self.uow_factory() as uow:
            owner, privacy, rel = self._subject(uow, viewer, handle)
        if not d.can_view(d.Section.PROFILE, d.Visibility(privacy.profile), rel):
            return {**card(owner), "profile_visibility": privacy.profile}
        return {**card(owner), "profile_visibility": privacy.profile, "bio": owner.bio,
                "member_since": owner.created_at.astimezone(timezone.utc).strftime("%Y-%m"),
                "sections": {"wardrobe": privacy.wardrobe, "friends_list": privacy.friends_list}}

    def public_wardrobe(self, viewer: Principal | None, handle: str, *, limit: int | None,
                        cursor: str | None) -> dict:
        n = check_limit(limit)
        with self.uow_factory() as uow:
            owner, privacy, rel = self._subject(uow, viewer, handle)
            if not d.can_view(d.Section.WARDROBE, d.Visibility(privacy.wardrobe), rel):
                raise _not_found()
            scope = f"profile.wardrobe:{owner.user_id}"
            vid = viewer.user_id if viewer else None
            after = decode_sealed(self.ring, cursor, principal=vid, scope=scope) if cursor else None
            rows = uow.owned.presentations(owner.user_id, after, n + 1)
        page, more = rows[:n], len(rows) > n
        nxt = encode_sealed(self.ring, principal=vid, scope=scope, pos=page[-1].position) if more else None
        return {"items": [{"product": r.product} for r in page], "next_cursor": nxt}

    def public_friends(self, viewer: Principal | None, handle: str, *, limit: int | None,
                       cursor: str | None) -> dict:
        n = check_limit(limit)
        with self.uow_factory() as uow:
            owner, privacy, rel = self._subject(uow, viewer, handle)
            if not d.can_view(d.Section.FRIENDS_LIST, d.Visibility(privacy.friends_list), rel):
                raise _not_found()
            scope = f"profile.friends:{owner.user_id}"
            vid = viewer.user_id if viewer else None
            after = decode_sealed(self.ring, cursor, principal=vid, scope=scope) if cursor else None
            rows = uow.accounts.list_friends(owner.user_id, after, n + 1, owner_view=rel is d.Relation.SELF,
                                             viewer=vid)
        page, more = rows[:n], len(rows) > n
        nxt = encode_sealed(self.ring, principal=vid, scope=scope, pos=page[-1].position) if more else None
        return {"friends": [card(r) for r in page], "next_cursor": nxt}

    def search(self, principal: Principal, q: str) -> dict:
        raw = (q or "").strip().lower()
        exact = raw.startswith("@")
        raw = raw.lstrip("@")
        if len(raw) < d.SEARCH_MIN_PREFIX and not exact or not raw or len(raw) > 20 or not raw.isascii():
            raise validation_failed([FieldError("query.q", "too_short",
                                                f"Search needs at least {d.SEARCH_MIN_PREFIX} characters.")])
        with self.uow_factory() as uow:
            self._onboarded(uow, principal)
            rows = uow.accounts.search(raw, exact or len(raw) == 20, principal.user_id, d.SEARCH_LIMIT)
            uow.commit()
        return {"results": [card(r) for r in rows]}

    # ------------------------------------------------------------------ friend requests
    def _befriend(self, uow: AccountsUoW, a: uuid.UUID, b: uuid.UUID, now) -> None:
        if uow.accounts.count_friends(a) >= d.MAX_FRIENDS or uow.accounts.count_friends(b) >= d.MAX_FRIENDS:
            raise d.friend_limit()
        uow.accounts.add_friendship(a, b, now)

    def send_request(self, principal: Principal, *, handle: str, idem_key: str) -> Outcome:
        me = principal.user_id
        with self.uow_factory() as uow:
            self._onboarded(uow, principal)
            uow.commit()

        def admit(uow: AccountsUoW, rec):
            if rec.attempt_reserved:
                return None
            retry = uow.attempts.reserve([AttemptScope("friend_request", str(me), d.FRIEND_REQUESTS_PER_DAY)],
                                         now=self.clock(), window=d.FRIEND_REQUEST_WINDOW, idempotency_id=rec.id)
            if retry is not None:
                return rate_limited(retry)
            uow.idempotency.mark_attempt_reserved(rec.id)
            return None

        def execute(uow: AccountsUoW, rec):
            now = self.clock()
            target = self._target(uow, me, handle)
            locked = uow.accounts.lock_profiles(me, target.user_id)
            if target.user_id not in locked:
                raise _not_found()
            rel = uow.accounts.relationship(me, target.user_id)
            if rel.blocked:
                raise _not_found()
            if rel.friends:
                raise conflict("ALREADY_FRIENDS", "You are already friends.")
            reverse = uow.accounts.pending(target.user_id, me)
            if reverse is not None:  # requests crossed: accept theirs instead of creating a second one
                self._befriend(uow, me, target.user_id, now)
                uow.accounts.set_request_status(reverse.id, "accepted", now)
                return 200, {"status": "accepted", "account": card(target)}
            existing = uow.accounts.pending(me, target.user_id)
            if existing is not None:
                return 200, {"status": "pending", "request_id": str(existing.id), "account": card(target)}
            theirs = d.effective_settings(uow.accounts.settings(target.user_id)[0])
            if theirs["friend_requests_from"] == "nobody":
                raise conflict("REQUESTS_CLOSED", "This account is not accepting friend requests.")
            if uow.accounts.count_pending_outgoing(me) >= d.MAX_PENDING_OUTGOING:
                raise conflict("PENDING_LIMIT_REACHED", f"At most {d.MAX_PENDING_OUTGOING} pending requests.")
            req = uow.accounts.create_request(me, target.user_id, now)
            return 201, {"status": "pending", "request_id": str(req.id), "account": card(target)}

        return self.executor.run(actor_id=me, route=ROUTE_SEND, key=idem_key,
                                 body={"handle": handle.strip().lower()}, admit=admit, execute=execute)

    def list_requests(self, principal: Principal, *, direction: str, limit: int | None, cursor: str | None) -> dict:
        n = check_limit(limit)
        scope = f"me.requests.{direction}"
        after = decode(self.ring, cursor, principal=principal.user_id, scope=scope, filter_key="") if cursor else None
        with self.uow_factory() as uow:
            rows = uow.accounts.list_requests(principal.user_id, direction, after, n + 1)
        page, more = rows[:n], len(rows) > n
        nxt = encode(self.ring, principal=principal.user_id, scope=scope, filter_key="",
                     pos=page[-1].position) if more else None
        return {"requests": [{"request_id": str(r.request_id), "account": card(r),
                              "created_at": r.position.created_at.isoformat()} for r in page], "next_cursor": nxt}

    def _transition(self, principal: Principal, request_id: uuid.UUID | None, action: str) -> dict:
        me = principal.user_id
        now = self.clock()
        with self.uow_factory() as uow:
            self._onboarded(uow, principal)
            req = uow.accounts.get_request(request_id) if request_id else None
            mine = req is not None and (req.to_user == me if action in ("accept", "decline") else req.from_user == me)
            if not mine:
                raise not_found("Request not found.")
            other = req.from_user if req.to_user == me else req.to_user
            uow.accounts.lock_profiles(me, other)  # lock order: profiles first, then the request row
            req = uow.accounts.get_request(req.id, lock=True)
            done = {"accept": "accepted", "decline": "declined", "cancel": "cancelled"}[action]
            if req.status == done:
                uow.commit()
                return {"status": done}
            if req.status != "pending":
                raise conflict("REQUEST_NOT_PENDING", "This request is no longer pending.")
            if action == "accept":
                if uow.accounts.relationship(me, other).blocked:
                    raise not_found("Request not found.")
                self._befriend(uow, me, other, now)
            uow.accounts.set_request_status(req.id, done, now)
            uow.commit()
        return {"status": done}

    def accept(self, principal: Principal, request_id: uuid.UUID | None) -> dict:
        return self._transition(principal, request_id, "accept")

    def decline(self, principal: Principal, request_id: uuid.UUID | None) -> dict:
        return self._transition(principal, request_id, "decline")

    def cancel(self, principal: Principal, request_id: uuid.UUID | None) -> dict:
        return self._transition(principal, request_id, "cancel")

    # ------------------------------------------------------------------ friends & blocks
    def my_friends(self, principal: Principal, *, limit: int | None, cursor: str | None) -> dict:
        n = check_limit(limit)
        scope = "me.friends"
        after = decode(self.ring, cursor, principal=principal.user_id, scope=scope, filter_key="") if cursor else None
        with self.uow_factory() as uow:
            rows = uow.accounts.list_friends(principal.user_id, after, n + 1, owner_view=True, viewer=None)
        page, more = rows[:n], len(rows) > n
        nxt = encode(self.ring, principal=principal.user_id, scope=scope, filter_key="",
                     pos=page[-1].position) if more else None
        return {"friends": [card(r) for r in page], "next_cursor": nxt}

    def remove_friend(self, principal: Principal, handle: str) -> None:
        with self.uow_factory() as uow:
            self._onboarded(uow, principal)
            t = self._target(uow, principal.user_id, handle)
            uow.accounts.lock_profiles(principal.user_id, t.user_id)
            uow.accounts.remove_friendship(principal.user_id, t.user_id)
            uow.commit()

    def block(self, principal: Principal, handle: str) -> None:
        me = principal.user_id
        with self.uow_factory() as uow:
            self._onboarded(uow, principal)
            t = self._target(uow, me, handle)
            uow.accounts.lock_profiles(me, t.user_id)
            if not uow.accounts.is_blocking(me, t.user_id) and uow.accounts.count_blocks(me) >= d.MAX_BLOCKS:
                raise conflict("BLOCK_LIMIT_REACHED", f"At most {d.MAX_BLOCKS} blocked accounts.")
            uow.accounts.remove_friendship(me, t.user_id)
            self.faults("block.after_unfriend")
            uow.accounts.delete_requests_between(me, t.user_id)
            self.faults("block.after_requests")
            uow.accounts.add_block(me, t.user_id, self.clock())
            uow.commit()

    def unblock(self, principal: Principal, handle: str) -> None:
        with self.uow_factory() as uow:
            self._onboarded(uow, principal)
            t = self._target(uow, principal.user_id, handle)
            uow.accounts.remove_block(principal.user_id, t.user_id)
            uow.commit()

    def my_blocks(self, principal: Principal, *, limit: int | None, cursor: str | None) -> dict:
        n = check_limit(limit)
        scope = "me.blocks"
        after = decode(self.ring, cursor, principal=principal.user_id, scope=scope, filter_key="") if cursor else None
        with self.uow_factory() as uow:
            rows = uow.accounts.list_blocks(principal.user_id, after, n + 1)
        page, more = rows[:n], len(rows) > n
        nxt = encode(self.ring, principal=principal.user_id, scope=scope, filter_key="",
                     pos=page[-1].position) if more else None
        return {"blocks": [card(r) for r in page], "next_cursor": nxt}

    # ------------------------------------------------------------------ settings (add-wearhouse-settings-security)
    @staticmethod
    def _settings_view(stored: dict, version: int, updated_at) -> dict:
        return {"version": version, "updated_at": updated_at.isoformat() if updated_at else None,
                "values": d.effective_settings(stored), "sections": list(d.SETTING_SECTIONS),
                "schema": d.settings_schema()}

    def get_settings(self, principal: Principal) -> dict:
        with self.uow_factory() as uow:
            self._own(uow, principal)
            stored, version, updated = uow.accounts.settings(principal.user_id)
            uow.commit()
        return self._settings_view(stored, version, updated)

    def update_settings(self, principal: Principal, *, version: int, values: dict) -> dict:
        errors = d.setting_errors(values)
        if not values:
            errors.append(FieldError("body.values", "empty", "Send at least one setting."))
        if errors:
            raise validation_failed(errors)
        now = self.clock()
        with self.uow_factory() as uow:
            self._own(uow, principal)
            stored, current, _ = uow.accounts.settings(principal.user_id)
            if version != current:
                raise conflict("SETTINGS_CHANGED", "Your settings were changed on another device. Reload and try again.")
            changed = sorted(k for k, v in values.items() if d.effective_settings(stored)[k] != v)
            merged = {**{k: v for k, v in stored.items() if k in d.SETTINGS}, **values}
            if uow.accounts.save_settings(principal.user_id, merged, version, now) is None:
                raise conflict("SETTINGS_CHANGED", "Your settings were changed on another device. Reload and try again.")
            if changed:
                uow.audit.record(actor_id=principal.user_id, action="account.settings_changed", target_type="user",
                                 target_id=str(principal.user_id), details={"keys": changed})
            stored, version, updated = uow.accounts.settings(principal.user_id)
            uow.commit()
        return self._settings_view(stored, version, updated)

    # ------------------------------------------------------------------ security overview
    def security(self, principal: Principal) -> dict:
        now = self.clock()
        with self.uow_factory() as uow:
            self._own(uow, principal)
            account = uow.directory.timeline(principal.user_id) or {}
            events = uow.accounts.security_events(principal.user_id, d.SECURITY_ACTIONS, 50)
            uow.commit()
        issued = principal.issued_at
        return {
            "account_created_at": account["created_at"].isoformat() if account.get("created_at") else None,
            "sessions_revoked_at": account["tokens_not_before"].isoformat() if account.get("tokens_not_before") else None,
            "current_session": {"signed_in_at": issued.isoformat() if issued else None,
                                "age_seconds": int((now - issued).total_seconds()) if issued else None,
                                "recent_enough_for_sensitive_actions": bool(issued and now - issued <= d.RECENT_AUTH)},
            "password_managed_by": "identity provider (Neon Auth); Wearhouse never receives your password",
            "events": [{"action": e["action"], "at": e["created_at"].isoformat(),
                        "by_you": e["actor_id"] == principal.user_id,
                        "details": {k: v for k, v in (e["details"] or {}).items() if k in ("keys", "handle", "role")}}
                       for e in events],
        }

    # ------------------------------------------------------------------ lifecycle
    def revoke_all(self, principal: Principal) -> None:
        now = self.clock().replace(microsecond=0)  # token iat has second resolution
        with self.uow_factory() as uow:
            uow.directory.revoke_tokens(principal.user_id, now)
            uow.audit.record(actor_id=principal.user_id, action="account.sessions_revoked", target_type="user",
                             target_id=str(principal.user_id))
            uow.commit()

    def export(self, principal: Principal) -> dict:
        me = principal.user_id
        with self.uow_factory() as uow:
            retry = uow.attempts.reserve([AttemptScope("export", str(me), d.EXPORTS_PER_HOUR)], now=self.clock(),
                                         window=d.EXPORT_WINDOW, idempotency_id=None)
            if retry is not None:
                uow.commit()
                raise rate_limited(retry)
            p = self._own(uow, principal)
            account = uow.directory.lock(me) or {}
            doc = {
                "format": "wearhouse.account-export/1",
                "generated_at": self.clock().isoformat(),
                "account": {"user_id": str(me), "created_at": account.get("created_at").isoformat()
                            if account.get("created_at") else None,
                            "roles": sorted(r.value for r in principal.roles)},
                "profile": self._profile_view(p, uow.accounts.ensure_privacy(me)),
                "handle_holds": [{"handle": h, "available_at": t.isoformat()} for h, t in uow.accounts.holds_for(me)],
                "friends": [card(r) for r in uow.accounts.list_friends(me, None, d.MAX_FRIENDS, owner_view=True,
                                                                       viewer=None)],
                "requests": {dirn: [{"request_id": str(r.request_id), "account": card(r),
                                     "created_at": r.position.created_at.isoformat()}
                                    for r in uow.accounts.list_requests(me, dirn, None, d.MAX_PENDING_OUTGOING + 1000)]
                             for dirn in ("incoming", "outgoing")},
                "blocks": [card(r) for r in uow.accounts.list_blocks(me, None, d.MAX_BLOCKS)],
                "owned_items": [item_view(item_id=r.id, serial=r.public_serial, presentation=r.presentation,
                                          claimed_at=r.claimed_at) for r in uow.owned.private_items(me)],
            }
            for name, section in self.export_sections.items():
                doc[name] = section(uow, me)
            stored, version, _ = uow.accounts.settings(me)
            doc["settings"] = {"version": version, "values": d.effective_settings(stored)}
            uow.audit.record(actor_id=me, action="account.exported", target_type="user", target_id=str(me))
            uow.commit()
        return doc

    def delete_account(self, principal: Principal, *, confirm: str) -> None:
        me = principal.user_id
        now = self.clock()
        if principal.issued_at is None or now - principal.issued_at > d.RECENT_AUTH:
            raise d.reauthentication_required()
        with self.uow_factory() as uow:
            p = self._own(uow, principal)
            expected = p.handle or "DELETE"
            if confirm != expected:
                raise validation_failed([FieldError("body.confirm", "confirmation_mismatch",
                                                    "Type your handle (or DELETE) to confirm.")])
            if uow.directory.lock(me) is None:
                raise not_found("Account not found.")
            if p.handle:
                uow.accounts.put_hold(p.handle, me, now + d.HANDLE_HOLD)
            uow.accounts.delete_account_data(me)
            uow.accounts.erase_settings(me)
            for erase in self.erasers:
                erase(uow, me)
            self.faults("delete.after_social")
            uow.directory.tombstone(me, now)
            self.faults("delete.after_tombstone")
            uow.audit.record(actor_id=me, action="account.deleted", target_type="user", target_id=str(me))
            uow.outbox.emit(event_type="account.deleted", aggregate_type="user", aggregate_id=me, payload={})
            uow.commit()


# ================================================================ staff role administration (add-wearhouse-object-management)
STAFF_ROLES = ("catalogue_editor", "inventory_manager", "moderator", "admin")


class StaffRolesService:
    """Admins (identity:manage_roles) grant/revoke staff roles by handle. Roles are read per request, so a change
    applies on the target's very next request. The last admin cannot be removed; admins cannot drop their own."""

    def __init__(self, uow_factory: Callable[[], AccountsUoW], *, clock: Clock = utcnow):
        self.uow_factory = uow_factory
        self.clock = clock

    def _view(self, uow: AccountsUoW, user_id: uuid.UUID, roles) -> dict:
        p = uow.accounts.get_profile(user_id)
        return {"handle": p.handle if p else None, "display_name": p.display_name if p else None,
                "roles": sorted(roles), "capabilities": sorted(
                    c.value for c in Principal(user_id, "", "", parse_roles(roles)).capabilities)}

    def staff(self, principal: Principal) -> list[dict]:
        require(principal, Capability.MANAGE_ROLES)
        with self.uow_factory() as uow:
            out = [self._view(uow, uid, roles) for uid, roles in uow.identity.staff().items()]
        return sorted(out, key=lambda x: (x["handle"] is None, x["handle"] or ""))

    def _target(self, uow: AccountsUoW, handle: str):
        p = uow.accounts.profile_by_handle((handle or "").strip().lower())
        if p is None:
            raise not_found("Account not found.")
        return p

    def lookup(self, principal: Principal, handle: str) -> dict:
        require(principal, Capability.MANAGE_ROLES)
        with self.uow_factory() as uow:
            p = self._target(uow, handle)
            return self._view(uow, p.user_id, uow.identity.roles(p.user_id))

    def _check_role(self, role: str) -> None:
        if role not in STAFF_ROLES:
            raise validation_failed([FieldError("path.role", "invalid", "Role must be one of: " + ", ".join(STAFF_ROLES))])

    def grant(self, principal: Principal, handle: str, role: str) -> dict:
        require(principal, Capability.MANAGE_ROLES)
        self._check_role(role)
        with self.uow_factory() as uow:
            p = self._target(uow, handle)
            changed = uow.identity.grant(p.user_id, role, f"admin:{principal.user_id}", self.clock())
            uow.audit.record(actor_id=principal.user_id, action="identity.role_granted", target_type="user",
                             target_id=str(p.user_id), details={"role": role, "changed": changed, "via": "admin_api"})
            uow.commit()
            return self._view(uow, p.user_id, uow.identity.roles(p.user_id))

    def revoke(self, principal: Principal, handle: str, role: str) -> dict:
        require(principal, Capability.MANAGE_ROLES)
        self._check_role(role)
        with self.uow_factory() as uow:
            p = self._target(uow, handle)
            if role == "admin":
                admins = uow.identity.lock_admins()  # serialises concurrent admin revocations
                if p.user_id in admins and len(admins) <= 1:
                    raise conflict("LAST_ADMIN", "The last admin cannot be removed; grant another admin first.")
                if p.user_id == principal.user_id:
                    raise conflict("SELF_REVOKE", "Admins cannot remove their own admin role; ask another admin.")
            changed = uow.identity.revoke(p.user_id, role)
            uow.audit.record(actor_id=principal.user_id, action="identity.role_revoked", target_type="user",
                             target_id=str(p.user_id), details={"role": role, "changed": changed, "via": "admin_api"})
            uow.commit()
            return self._view(uow, p.user_id, uow.identity.roles(p.user_id))
