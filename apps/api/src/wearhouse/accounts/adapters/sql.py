from __future__ import annotations

from sqlalchemy import and_, case, delete, exists, func, insert, literal, or_, select, tuple_, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError

from ...platform.ids import new_id
from ...platform.pagination import Position
from ..ports import HandleTaken, ListedAccount, PrivacyRow, ProfileRow, Relationship, RequestRow
from ...platform.tables import audit_event
from .tables import (account_profile, account_setting, friend_request, friendship, handle_hold, privacy_setting,
                     user_block)

P = account_profile


def _profile(r) -> ProfileRow:
    return ProfileRow(r.user_id, r.handle, r.display_name, r.bio, r.avatar_kind, r.avatar_preset, r.avatar_url,
                      r.handle_changed_at, r.created_at)


def _listed(r, created_at, other, request_id=None) -> ListedAccount:
    return ListedAccount(Position(created_at, other), r.user_id, r.handle, r.display_name, r.avatar_kind,
                         r.avatar_preset, r.avatar_url, request_id)


def _blocked_between(a, b):
    return exists().where(or_(and_(user_block.c.blocker == a, user_block.c.blocked == b),
                              and_(user_block.c.blocker == b, user_block.c.blocked == a)))


class SqlAccountsRepository:
    def __init__(self, conn: Connection):
        self.conn = conn

    # ------------------------------------------------------------------ profiles
    def ensure_profile(self, user_id, display_name, now):
        self.conn.execute(pg_insert(P).values(user_id=user_id, display_name=display_name, created_at=now,
                                              updated_at=now).on_conflict_do_nothing(index_elements=["user_id"]))
        return self.get_profile(user_id)

    def get_profile(self, user_id):
        r = self.conn.execute(select(P).where(P.c.user_id == user_id)).one_or_none()
        return _profile(r) if r else None

    def profile_by_handle(self, handle):
        r = self.conn.execute(select(P).where(P.c.handle == handle)).one_or_none()
        return _profile(r) if r else None

    def lock_profiles(self, *user_ids):
        rows = self.conn.execute(select(P).where(P.c.user_id.in_(list(user_ids))).order_by(P.c.user_id)
                                 .with_for_update()).all()
        return {r.user_id: _profile(r) for r in rows}

    def update_profile(self, user_id, values, now):
        sp = self.conn.begin_nested()
        try:
            self.conn.execute(update(P).where(P.c.user_id == user_id).values(**values, updated_at=now))
            sp.commit()
        except IntegrityError as exc:
            sp.rollback()
            if "uq_account_profile_handle" in str(exc.orig):
                raise HandleTaken() from None
            raise
        return self.get_profile(user_id)

    def get_hold(self, handle):
        r = self.conn.execute(select(handle_hold.c.held_for, handle_hold.c.available_at)
                              .where(handle_hold.c.handle == handle).with_for_update()).one_or_none()
        return (r.held_for, r.available_at) if r else None

    def put_hold(self, handle, held_for, available_at):
        stmt = pg_insert(handle_hold).values(handle=handle, held_for=held_for, available_at=available_at)
        self.conn.execute(stmt.on_conflict_do_update(index_elements=["handle"],
                                                     set_={"held_for": held_for, "available_at": available_at}))

    def delete_hold(self, handle):
        self.conn.execute(delete(handle_hold).where(handle_hold.c.handle == handle))

    def holds_for(self, user_id):
        rows = self.conn.execute(select(handle_hold.c.handle, handle_hold.c.available_at)
                                 .where(handle_hold.c.held_for == user_id).order_by(handle_hold.c.available_at)).all()
        return [(r.handle, r.available_at) for r in rows]

    def search(self, prefix, exact, viewer, limit):
        cond = P.c.handle == prefix if exact else and_(P.c.handle.like(
            prefix.replace("\\", "\\\\").replace("_", "\\_").replace("%", "\\%") + "%", escape="\\"),
            ~exists().where(account_setting.c.user_id == P.c.user_id,  # discoverable=false: exact @handle only
                            account_setting.c["values"].contains({"discoverable": False})))
        q = (select(P).where(cond, P.c.handle.is_not(None), ~_blocked_between(viewer, P.c.user_id))
             .order_by(P.c.handle).limit(limit))
        return [_profile(r) for r in self.conn.execute(q).all()]

    # ------------------------------------------------------------------ privacy
    def ensure_privacy(self, user_id):
        self.conn.execute(pg_insert(privacy_setting).values(user_id=user_id)
                          .on_conflict_do_nothing(index_elements=["user_id"]))
        r = self.conn.execute(select(privacy_setting).where(privacy_setting.c.user_id == user_id)).one()
        return PrivacyRow(r.profile, r.wardrobe, r.friends_list)

    def set_privacy(self, user_id, row, now):
        self.ensure_privacy(user_id)
        self.conn.execute(update(privacy_setting).where(privacy_setting.c.user_id == user_id)
                          .values(profile=row.profile, wardrobe=row.wardrobe, friends_list=row.friends_list,
                                  updated_at=now))
        return self.ensure_privacy(user_id)

    # ------------------------------------------------------------------ relationships
    def relationship(self, a, b):
        lo, hi = sorted((a, b))
        blocked = self.conn.execute(select(_blocked_between(a, b))).scalar()
        friends = self.conn.execute(select(exists().where(friendship.c.user_low == lo,
                                                          friendship.c.user_high == hi))).scalar()
        return Relationship(bool(blocked), bool(friends))

    @staticmethod
    def _req(r) -> RequestRow:
        return RequestRow(r.id, r.from_user, r.to_user, r.status, r.created_at)

    def pending(self, from_user, to_user):
        r = self.conn.execute(select(friend_request).where(
            friend_request.c.from_user == from_user, friend_request.c.to_user == to_user,
            friend_request.c.status == "pending")).one_or_none()
        return self._req(r) if r else None

    def get_request(self, request_id, *, lock=False):
        q = select(friend_request).where(friend_request.c.id == request_id)
        r = self.conn.execute(q.with_for_update() if lock else q).one_or_none()
        return self._req(r) if r else None

    def create_request(self, from_user, to_user, now):
        rid = new_id()
        self.conn.execute(insert(friend_request).values(id=rid, from_user=from_user, to_user=to_user,
                                                        status="pending", created_at=now))
        return RequestRow(rid, from_user, to_user, "pending", now)

    def set_request_status(self, request_id, status, now):
        self.conn.execute(update(friend_request).where(friend_request.c.id == request_id)
                          .values(status=status, resolved_at=now))

    def count_pending_outgoing(self, user_id):
        return self.conn.execute(select(func.count()).select_from(friend_request).where(
            friend_request.c.from_user == user_id, friend_request.c.status == "pending")).scalar()

    def list_requests(self, user_id, direction, after, limit):
        me, other = ((friend_request.c.to_user, friend_request.c.from_user) if direction == "incoming"
                     else (friend_request.c.from_user, friend_request.c.to_user))
        q = (select(P, friend_request.c.id.label("rid"), friend_request.c.created_at.label("rcreated"))
             .select_from(friend_request.join(P, P.c.user_id == other))
             .where(me == user_id, friend_request.c.status == "pending"))
        if after is not None:
            q = q.where(tuple_(friend_request.c.created_at, friend_request.c.id) > tuple_(after.created_at, after.id))
        rows = self.conn.execute(q.order_by(friend_request.c.created_at, friend_request.c.id).limit(limit)).all()
        return [_listed(r, r.rcreated, r.rid, request_id=r.rid) for r in rows]

    def accepted_outgoing(self, user_id, since, limit):
        q = (select(P, friend_request.c.id.label("rid"), friend_request.c.resolved_at.label("resolved"))
             .select_from(friend_request.join(P, P.c.user_id == friend_request.c.to_user))
             .where(friend_request.c.from_user == user_id, friend_request.c.status == "accepted",
                    friend_request.c.resolved_at >= since)
             .order_by(friend_request.c.resolved_at.desc(), friend_request.c.id.desc()).limit(limit))
        return [_listed(r, r.resolved, r.rid, request_id=r.rid) for r in self.conn.execute(q).all()]

    def add_friendship(self, a, b, now):
        lo, hi = sorted((a, b))
        r = self.conn.execute(pg_insert(friendship).values(user_low=lo, user_high=hi, created_at=now)
                              .on_conflict_do_nothing().returning(friendship.c.user_low)).scalar_one_or_none()
        return r is not None

    def remove_friendship(self, a, b):
        lo, hi = sorted((a, b))
        return self.conn.execute(delete(friendship).where(friendship.c.user_low == lo,
                                                          friendship.c.user_high == hi)).rowcount > 0

    def count_friends(self, user_id):
        return self.conn.execute(select(func.count()).select_from(friendship).where(
            or_(friendship.c.user_low == user_id, friendship.c.user_high == user_id))).scalar()

    def list_friends(self, user_id, after, limit, *, owner_view, viewer):
        other = case((friendship.c.user_low == user_id, friendship.c.user_high), else_=friendship.c.user_low)
        f = (select(friendship.c.created_at.label("fcreated"), other.label("other"))
             .where(or_(friendship.c.user_low == user_id, friendship.c.user_high == user_id)).subquery())
        q = (select(P, f.c.fcreated, f.c.other)
             .select_from(f.join(P, P.c.user_id == f.c.other)
                          .outerjoin(privacy_setting, privacy_setting.c.user_id == f.c.other)))
        if not owner_view:
            q = q.where(func.coalesce(privacy_setting.c.profile, literal("public")) != "private")
            if viewer is not None:
                q = q.where(~_blocked_between(viewer, f.c.other))
        if after is not None:
            q = q.where(tuple_(f.c.fcreated, f.c.other) > tuple_(after.created_at, after.id))
        rows = self.conn.execute(q.order_by(f.c.fcreated, f.c.other).limit(limit)).all()
        return [_listed(r, r.fcreated, r.other) for r in rows]

    def delete_requests_between(self, a, b):
        return self.conn.execute(delete(friend_request).where(
            friend_request.c.status == "pending",
            or_(and_(friend_request.c.from_user == a, friend_request.c.to_user == b),
                and_(friend_request.c.from_user == b, friend_request.c.to_user == a)))).rowcount

    def add_block(self, blocker, blocked, now):
        r = self.conn.execute(pg_insert(user_block).values(blocker=blocker, blocked=blocked, created_at=now)
                              .on_conflict_do_nothing().returning(user_block.c.blocker)).scalar_one_or_none()
        return r is not None

    def remove_block(self, blocker, blocked):
        return self.conn.execute(delete(user_block).where(user_block.c.blocker == blocker,
                                                          user_block.c.blocked == blocked)).rowcount > 0

    def count_blocks(self, user_id):
        return self.conn.execute(select(func.count()).select_from(user_block)
                                 .where(user_block.c.blocker == user_id)).scalar()

    def is_blocking(self, blocker, blocked):
        return bool(self.conn.execute(select(exists().where(user_block.c.blocker == blocker,
                                                            user_block.c.blocked == blocked))).scalar())

    def list_blocks(self, user_id, after, limit):
        q = (select(P, user_block.c.created_at.label("bcreated"), user_block.c.blocked)
             .select_from(user_block.join(P, P.c.user_id == user_block.c.blocked))
             .where(user_block.c.blocker == user_id))
        if after is not None:
            q = q.where(tuple_(user_block.c.created_at, user_block.c.blocked) > tuple_(after.created_at, after.id))
        rows = self.conn.execute(q.order_by(user_block.c.created_at, user_block.c.blocked).limit(limit)).all()
        return [_listed(r, r.bcreated, r.blocked) for r in rows]

    # ------------------------------------------------------------------ lifecycle
    def delete_account_data(self, user_id):
        self.conn.execute(delete(friend_request).where(or_(friend_request.c.from_user == user_id,
                                                           friend_request.c.to_user == user_id)))
        self.conn.execute(delete(friendship).where(or_(friendship.c.user_low == user_id,
                                                       friendship.c.user_high == user_id)))
        self.conn.execute(delete(user_block).where(or_(user_block.c.blocker == user_id,
                                                       user_block.c.blocked == user_id)))
        self.conn.execute(delete(privacy_setting).where(privacy_setting.c.user_id == user_id))
        self.conn.execute(delete(P).where(P.c.user_id == user_id))


    # ------------------------------------------------------------------ settings + security (add-wearhouse-settings-security)
    def settings(self, user_id):
        r = self.conn.execute(select(account_setting).where(account_setting.c.user_id == user_id)).one_or_none()
        return (dict(r._mapping["values"]), r.version, r.updated_at) if r else ({}, 0, None)

    def settings_for(self, user_ids):
        if not user_ids:
            return {}
        rows = self.conn.execute(select(account_setting.c.user_id, account_setting.c["values"])
                                 .where(account_setting.c.user_id.in_(list(user_ids))))
        return {r.user_id: dict(r._mapping["values"]) for r in rows}

    def save_settings(self, user_id, values, expected_version, now):
        """Compare-and-set on the version; returns the new version, or None when another save came first."""
        if expected_version == 0:
            r = self.conn.execute(pg_insert(account_setting).values(user_id=user_id, values=values, version=1,
                                                                    updated_at=now)
                                  .on_conflict_do_nothing(index_elements=["user_id"])
                                  .returning(account_setting.c.version)).first()
            return r.version if r else None
        r = self.conn.execute(update(account_setting)
                              .where(account_setting.c.user_id == user_id, account_setting.c.version == expected_version)
                              .values(values=values, version=account_setting.c.version + 1, updated_at=now)
                              .returning(account_setting.c.version)).first()
        return r.version if r else None

    def erase_settings(self, user_id):
        self.conn.execute(delete(account_setting).where(account_setting.c.user_id == user_id))

    def security_events(self, user_id, actions, limit):
        mine = and_(audit_event.c.actor_id == user_id, audit_event.c.action.in_(actions))
        about_me = and_(audit_event.c.target_type == "user", audit_event.c.target_id == str(user_id),
                        audit_event.c.action.in_(("identity.role_granted", "identity.role_revoked")))
        rows = self.conn.execute(select(audit_event.c.action, audit_event.c.details, audit_event.c.created_at,
                                        audit_event.c.actor_id)
                                 .where(or_(mine, about_me))
                                 .order_by(audit_event.c.created_at.desc(), audit_event.c.id.desc()).limit(limit))
        return [dict(r._mapping) for r in rows]
