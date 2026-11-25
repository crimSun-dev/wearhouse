"""Social services: look shares, week plan sharing, friends feed, derived notifications and profile showcase.

Visibility is ALWAYS computed at read time with the accounts policy (`can_view`) and the owner's wardrobe privacy as
a ceiling (design D1), so unfriending, blocking or tightening privacy applies on the very next read. Projections come
from the wardrobe application layer and never contain serials, keys, item ids, photos, care, wear or location.
Nothing here creates items, credentials, wishlist or cart entries for a viewer (inspiration never grants items).
"""
from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Callable

from ..accounts.domain import (MAX_FRIENDS, NOTIFICATION_SETTING, Relation, Section, Visibility, can_view,
                               relation_of)
from ..accounts.domain import effective_settings as account_settings
from ..accounts.application import card
from ..accounts.ports import Relationship
from ..identity.domain import Capability, require
from ..platform.clock import Clock, utcnow
from ..platform.crypto import KeyRing
from ..platform.errors import FieldError, conflict, not_found, validation_failed
from ..platform.ids import new_id
from ..platform.pagination import Position, check_limit, decode_sealed, encode_sealed
from ..wardrobe.application import WardrobeService
from ..weather.application import local_today
from .ports import ShareRow, SocialUoW

AUDIENCES = ("friends", "public")
PLAN_AUDIENCES = ("none", "friends")
ACCENTS = ("plum", "ivory", "blush", "noir", "sage", "sky")
STRICTNESS = {"public": 0, "friends": 1, "private": 2}
MAX_ACTIVE_SHARES = 100
MAX_FEATURED = 3
NOTIFY_WINDOW = timedelta(days=30)
MAX_NOTIFICATIONS = 50
FEED_SCOPE = "me.feed"


def _iso(x):
    return x.isoformat() if x else None


def _gone() -> Exception:
    return not_found("Share not found.")


class SocialService:
    def __init__(self, uow_factory: Callable[[], SocialUoW], ring: KeyRing, wardrobe: WardrobeService, *,
                 clock: Clock = utcnow):
        self.uow_factory = uow_factory
        self.ring = ring
        self.wardrobe = wardrobe
        self.clock = clock

    # ================================================================ policy (design D1)
    def _relation(self, uow: SocialUoW, owner: uuid.UUID, viewer: uuid.UUID | None) -> Relation:
        if viewer == owner:
            return Relation.SELF
        rel = uow.accounts.relationship(owner, viewer) if viewer else Relationship(False, False)
        return relation_of(is_self=False, viewer_known=viewer is not None, blocked=rel.blocked, friends=rel.friends)

    def _visible(self, uow: SocialUoW, owner: uuid.UUID, viewer: uuid.UUID | None, audience: str) -> bool:
        if viewer == owner:
            return True
        if uow.accounts.get_profile(owner) is None:  # deleted / never onboarded owner
            return False
        ceiling = uow.accounts.ensure_privacy(owner).wardrobe
        effective = max(audience, ceiling, key=STRICTNESS.__getitem__)
        return can_view(Section.WARDROBE, Visibility(effective), self._relation(uow, owner, viewer))

    def _can_see(self, uow: SocialUoW, s: ShareRow, viewer: uuid.UUID | None) -> bool:
        """Live share + read-time visibility; a moderated (hidden) share is visible to its owner only."""
        if s.revoked_at is not None:
            return False
        if viewer == s.owner_id:
            return True
        return s.moderation_state == "visible" and self._visible(uow, s.owner_id, viewer, s.audience)

    def _share_view(self, uow: SocialUoW, s: ShareRow, *, owner_view: bool = False) -> dict:
        profile = uow.accounts.get_profile(s.owner_id)
        view = {"id": str(s.id), "owner": card(profile) if profile else None, "caption": s.caption,
                "audience": s.audience, "created_at": _iso(s.created_at),
                "look": self.wardrobe.projection(uow, s.owner_id, s.revision_id)}
        if owner_view:  # the owner also sees what the privacy ceiling leaves of the audience (private = nobody)
            ceiling = uow.accounts.ensure_privacy(s.owner_id).wardrobe
            view.update({"look_id": str(s.look_id), "revoked": s.revoked_at is not None,
                         "moderation": s.moderation_state,
                         "effective_audience": max(s.audience, ceiling, key=STRICTNESS.__getitem__)})
        return view

    # ================================================================ my shares
    def share_look(self, principal, *, look_id: uuid.UUID, audience: str, caption: str | None) -> dict:
        self._check_audience(audience)
        caption = self._check_caption(caption)
        me = principal.user_id
        with self.uow_factory() as uow:
            lk = uow.wardrobe.look(me, look_id)
            if lk is None or lk.deleted_at is not None:
                raise validation_failed([FieldError("body.look_id", "unknown_look", "Unknown look.")])
            if uow.social.count_active(me) >= MAX_ACTIVE_SHARES:
                raise conflict("SHARES_FULL", f"At most {MAX_ACTIVE_SHARES} active shares.")
            rev = uow.wardrobe.revision_by_no(look_id, lk.current_revision_no)
            row = ShareRow(new_id(), me, look_id, rev.id, audience, caption, self.clock(), None)
            uow.social.insert_share(row)
            uow.audit.record(actor_id=me, action="social.look_shared", target_type="look_share",
                             target_id=str(row.id), details={"audience": audience})
            uow.commit()
            return self._share_view(uow, row, owner_view=True)

    def my_shares(self, principal) -> list[dict]:
        with self.uow_factory() as uow:
            return [self._share_view(uow, s, owner_view=True)
                    for s in uow.social.shares_of(principal.user_id, active_only=False, limit=200)]

    def update_share(self, principal, share_id: uuid.UUID, changes: dict) -> dict:
        me = principal.user_id
        with self.uow_factory() as uow:
            s = uow.social.share(share_id, lock=True)
            if s is None or s.owner_id != me or s.revoked_at is not None:
                raise _gone()
            values = {}
            if changes.get("audience") is not None:
                self._check_audience(changes["audience"])
                values["audience"] = changes["audience"]
            if "caption" in changes:
                values["caption"] = self._check_caption(changes["caption"])
            if changes.get("repin"):
                lk = uow.wardrobe.look(me, s.look_id)
                if lk is None or lk.deleted_at is not None:
                    raise conflict("LOOK_DELETED", "The look was deleted, so the share cannot be re-pinned.")
                values["revision_id"] = uow.wardrobe.revision_by_no(s.look_id, lk.current_revision_no).id
            if values:
                uow.social.update_share(share_id, values)
            uow.commit()
            return self._share_view(uow, uow.social.share(share_id), owner_view=True)

    def revoke_share(self, principal, share_id: uuid.UUID) -> None:
        with self.uow_factory() as uow:
            s = uow.social.share(share_id, lock=True)
            if s is None or s.owner_id != principal.user_id:
                raise _gone()
            if s.revoked_at is None:
                uow.social.update_share(share_id, {"revoked_at": self.clock()})
                uow.audit.record(actor_id=principal.user_id, action="social.share_revoked", target_type="look_share",
                                 target_id=str(share_id), details={})
            uow.commit()

    @staticmethod
    def _check_audience(audience: str) -> None:
        if audience not in AUDIENCES:
            raise validation_failed([FieldError("body.audience", "invalid", "Audience must be friends or public.")])

    @staticmethod
    def _check_caption(caption: str | None) -> str | None:
        caption = (caption or "").strip() or None
        if caption and len(caption) > 140:
            raise validation_failed([FieldError("body.caption", "too_long", "Captions are at most 140 characters.")])
        return caption

    # ================================================================ reading shares
    def read_share(self, viewer, share_id: uuid.UUID) -> dict:
        vid = viewer.user_id if viewer else None
        with self.uow_factory() as uow:
            s = uow.social.share(share_id)
            if s is None or not self._can_see(uow, s, vid):
                raise _gone()
            return self._share_view(uow, s, owner_view=vid == s.owner_id)

    def _owner_by_handle(self, uow: SocialUoW, handle: str):
        p = uow.accounts.profile_by_handle(handle.strip().lower())
        if p is None:
            raise not_found("Profile not found.")
        return p

    def profile_shares(self, viewer, handle: str) -> dict:
        vid = viewer.user_id if viewer else None
        with self.uow_factory() as uow:
            owner = self._owner_by_handle(uow, handle)
            if self._relation(uow, owner.user_id, vid) is Relation.BLOCKED:
                raise not_found("Profile not found.")
            shares = [s for s in uow.social.shares_of(owner.user_id, active_only=True, limit=50)
                      if self._can_see(uow, s, vid)]
            return {"items": [self._share_view(uow, s) for s in shares]}

    # ================================================================ week plan sharing
    def plan_sharing(self, principal) -> dict:
        with self.uow_factory() as uow:
            return {"audience": uow.social.plan_setting(principal.user_id)}

    def set_plan_sharing(self, principal, audience: str) -> dict:
        if audience not in PLAN_AUDIENCES:
            raise validation_failed([FieldError("body.audience", "invalid", "Audience must be none or friends.")])
        with self.uow_factory() as uow:
            uow.social.set_plan_setting(principal.user_id, audience, self.clock())
            uow.commit()
        return {"audience": audience}

    def week(self, viewer, handle: str) -> dict:
        vid = viewer.user_id if viewer else None
        with self.uow_factory() as uow:
            owner = self._owner_by_handle(uow, handle)
            if vid != owner.user_id:
                rel = self._relation(uow, owner.user_id, vid)
                ok = (rel is Relation.FRIEND and uow.social.plan_setting(owner.user_id) == "friends"
                      and uow.accounts.ensure_privacy(owner.user_id).wardrobe != "private")
                if not ok:
                    raise not_found("Profile not found.")
            days = self.wardrobe.week_projection(uow, owner.user_id, local_today(self.clock()))
            return {"owner": card(owner), "days": days}

    # ================================================================ friends feed
    def _friend_ids(self, uow: SocialUoW, me: uuid.UUID) -> list[uuid.UUID]:
        return [a.user_id for a in uow.accounts.list_friends(me, None, MAX_FRIENDS, owner_view=True, viewer=None)]

    def feed(self, principal, *, limit: int | None, cursor: str | None) -> dict:
        me = principal.user_id
        limit = check_limit(limit)
        after = decode_sealed(self.ring, cursor, principal=me, scope=FEED_SCOPE) if cursor else None
        with self.uow_factory() as uow:
            friends = self._friend_ids(uow, me)
            out: list[ShareRow] = []
            more = False
            while len(out) < limit:
                batch = uow.social.shares_by_owners(friends, after, limit + 1)
                if not batch:
                    break
                for s in batch:
                    if len(out) == limit:
                        more = True
                        break
                    after = Position(s.created_at, s.id)
                    if self._can_see(uow, s, me):
                        out.append(s)
                if more or len(batch) <= limit:
                    break
            items = [self._share_view(uow, s) for s in out]
        nxt = encode_sealed(self.ring, principal=me, scope=FEED_SCOPE,
                            pos=Position(out[-1].created_at, out[-1].id)) if more and out else None
        return {"items": items, "next_cursor": nxt}

    # ================================================================ notifications (derived, design D3)
    def _notifications(self, uow: SocialUoW, me: uuid.UUID) -> list[dict]:
        since = self.clock() - NOTIFY_WINDOW
        out = []
        for r in uow.accounts.list_requests(me, "incoming", None, 200):
            out.append({"kind": "friend_request", "at": r.position.created_at, "account": card(r),
                        "ref": str(r.request_id)})
        for r in uow.accounts.accepted_outgoing(me, since, MAX_NOTIFICATIONS):
            if not uow.accounts.relationship(me, r.user_id).blocked:
                out.append({"kind": "request_accepted", "at": r.position.created_at, "account": card(r),
                            "ref": str(r.request_id)})
        friends = self._friend_ids(uow, me)
        for s in uow.social.shares_by_owners(friends, None, 200, since=since):
            if self._can_see(uow, s, me):
                p = uow.accounts.get_profile(s.owner_id)
                out.append({"kind": "friend_shared_look", "at": s.created_at, "account": card(p), "ref": str(s.id)})
        prefs = account_settings(uow.accounts.settings(me)[0])  # add-wearhouse-settings-security
        out = [n for n in out if prefs[NOTIFICATION_SETTING[n["kind"]]]]
        out.sort(key=lambda n: n["at"], reverse=True)
        return out[:MAX_NOTIFICATIONS]

    def notifications(self, principal) -> dict:
        with self.uow_factory() as uow:
            items = self._notifications(uow, principal.user_id)
            marker = uow.social.read_through(principal.user_id)
        return {"read_through": _iso(marker),
                "items": [{**n, "at": n["at"].isoformat(), "unread": marker is None or n["at"] > marker} for n in items]}

    def unread_count(self, principal) -> dict:
        n = self.notifications(principal)
        return {"unread": sum(1 for i in n["items"] if i["unread"])}

    def mark_read(self, principal) -> dict:
        with self.uow_factory() as uow:
            uow.social.set_read_through(principal.user_id, self.clock())
            uow.commit()
        return {"unread": 0}

    # ================================================================ showcase
    def my_showcase(self, principal) -> dict:
        with self.uow_factory() as uow:
            sc = uow.social.showcase(principal.user_id) or {"headline": None, "accent": "plum", "featured": []}
            return sc

    def put_showcase(self, principal, *, headline: str | None, accent: str, featured: list[uuid.UUID]) -> dict:
        headline = (headline or "").strip() or None
        errors = []
        if headline and len(headline) > 80:
            errors.append(FieldError("body.headline", "too_long", "Headlines are at most 80 characters."))
        if accent not in ACCENTS:
            errors.append(FieldError("body.accent", "invalid", "Unknown accent preset."))
        if len(featured) > MAX_FEATURED or len(set(featured)) != len(featured):
            errors.append(FieldError("body.featured_share_ids", "invalid", f"Up to {MAX_FEATURED} distinct shares."))
        if errors:
            raise validation_failed(errors)
        with self.uow_factory() as uow:
            for sid in featured:
                s = uow.social.share(sid)
                if s is None or s.owner_id != principal.user_id or s.revoked_at is not None:
                    raise validation_failed([FieldError("body.featured_share_ids", "unknown_share",
                                                        "Feature only your own active shares.")])
            uow.social.put_showcase(principal.user_id, headline, accent, [str(s) for s in featured], self.clock())
            uow.commit()
        return self.my_showcase(principal)

    def showcase(self, viewer, handle: str) -> dict:
        vid = viewer.user_id if viewer else None
        with self.uow_factory() as uow:
            owner = self._owner_by_handle(uow, handle)
            relation = self._relation(uow, owner.user_id, vid)
            privacy = uow.accounts.ensure_privacy(owner.user_id)
            if not can_view(Section.PROFILE, Visibility(privacy.profile), relation):
                raise not_found("Profile not found.")
            sc = uow.social.showcase(owner.user_id) or {"headline": None, "accent": "plum", "featured": []}
            featured = []
            for sid in sc["featured"]:
                s = uow.social.share(uuid.UUID(sid))
                if s and self._can_see(uow, s, vid):
                    featured.append(self._share_view(uow, s))
            return {"owner": card(owner), "headline": sc["headline"], "accent": sc["accent"], "featured": featured}

    # ================================================================ reports + moderation (complete-wearhouse-tdd)
    def report_share(self, principal, share_id: uuid.UUID, reason: str) -> dict:
        reason = (reason or "").strip()
        if not 1 <= len(reason) <= 300:
            raise validation_failed([FieldError("body.reason", "invalid", "Give a reason of 1-300 characters.")])
        with self.uow_factory() as uow:
            s = uow.social.share(share_id)
            if s is None or not self._can_see(uow, s, principal.user_id):
                raise _gone()
            if s.owner_id == principal.user_id:
                raise validation_failed([FieldError("path.share_id", "own_share", "You cannot report your own share.")])
            if not uow.social.add_report(new_id(), share_id, principal.user_id, reason, self.clock()):
                raise conflict("ALREADY_REPORTED", "You already reported this share.")
            uow.commit()
        return {"share_id": str(share_id), "reported": True}

    def moderation_queue(self, principal, limit: int = 50) -> dict:
        require(principal, Capability.MODERATE)
        with self.uow_factory() as uow:
            out = []
            for r in uow.social.open_reports(limit):
                s = uow.social.share(r["share_id"])
                if s is None:
                    continue
                out.append({**self._share_view(uow, s), "moderation": s.moderation_state, "revoked": s.revoked_at is not None,
                            "reports": r["reports"], "reasons": r["reasons"],
                            "first_reported_at": _iso(r["first_reported_at"])})
        return {"items": out}

    def moderate(self, principal, share_id: uuid.UUID, *, action: str, reason: str) -> dict:
        """hide / restore / dismiss (reports only). Audited; moderators never touch keys, orders or wardrobes."""
        require(principal, Capability.MODERATE)
        reason = (reason or "").strip()
        if action not in ("hide", "restore", "dismiss") or not 1 <= len(reason) <= 300:
            raise validation_failed([FieldError("body", "invalid", "action must be hide, restore or dismiss, with a "
                                                                   "reason of 1-300 characters.")])
        now = self.clock()
        with self.uow_factory() as uow:
            s = uow.social.share(share_id, lock=True)
            if s is None:
                raise _gone()
            if action == "hide":
                uow.social.set_moderation(share_id, "hidden", principal.user_id, reason, now)
                uow.social.resolve_reports(share_id, "actioned", now)
            elif action == "restore":
                uow.social.set_moderation(share_id, "visible", principal.user_id, reason, now)
            else:
                uow.social.resolve_reports(share_id, "dismissed", now)
            uow.audit.record(actor_id=principal.user_id, action=f"social.share_{action}", target_type="look_share",
                             target_id=str(share_id), details={"reason": reason})
            uow.commit()
            s = uow.social.share(share_id)
        return {"share_id": str(share_id), "moderation": s.moderation_state}

    # ================================================================ inspiration (complete-wearhouse-tdd)
    MAX_INSPIRATIONS = 200

    def save_inspiration(self, principal, share_id: uuid.UUID) -> dict:
        """A private snapshot of a share's SAFE projection, saved while visible. It never grants the items."""
        with self.uow_factory() as uow:
            s = uow.social.share(share_id)
            if s is None or not self._can_see(uow, s, principal.user_id):
                raise _gone()
            if len(uow.social.inspirations(principal.user_id)) >= self.MAX_INSPIRATIONS:
                raise conflict("INSPIRATION_FULL", f"At most {self.MAX_INSPIRATIONS} saved inspirations.")
            view = self._share_view(uow, s)
            snapshot = {"from": view["owner"], "caption": view["caption"], "look": view["look"],
                        "shared_at": view["created_at"]}
            iid = new_id()
            uow.social.add_inspiration(iid, principal.user_id, share_id, snapshot, self.clock())
            uow.commit()
        return self._inspiration_view({"id": iid, "snapshot": snapshot, "created_at": self.clock()})

    @staticmethod
    def _inspiration_view(r: dict) -> dict:
        return {"id": str(r["id"]), "saved_at": _iso(r["created_at"]), **r["snapshot"]}

    def inspirations(self, principal) -> dict:
        with self.uow_factory() as uow:
            return {"items": [self._inspiration_view(r) for r in uow.social.inspirations(principal.user_id)]}

    def delete_inspiration(self, principal, inspiration_id: uuid.UUID) -> None:
        with self.uow_factory() as uow:
            if not uow.social.delete_inspiration(principal.user_id, inspiration_id):
                raise not_found("Inspiration not found.")
            uow.commit()

    # ================================================================ accounts integration
    def export_data(self, uow: SocialUoW, user_id: uuid.UUID) -> dict:
        return {"shares": [{"id": str(s.id), "look_id": str(s.look_id), "audience": s.audience, "caption": s.caption,
                            "created_at": _iso(s.created_at), "revoked_at": _iso(s.revoked_at)}
                           for s in uow.social.shares_of(user_id, active_only=False, limit=10_000)],
                "plan_sharing": uow.social.plan_setting(user_id),
                "inspirations": [self._inspiration_view(r) for r in uow.social.inspirations(user_id)],
                "reports_made": uow.social.reports_by(user_id),
                "showcase": uow.social.showcase(user_id)}
