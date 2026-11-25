from __future__ import annotations

from sqlalchemy import delete, func, insert, select, tuple_, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Connection

from ..ports import ShareRow
from .tables import inspiration, look_share, notification_state, plan_share_setting, profile_showcase, share_report

S = look_share


def _share(r) -> ShareRow:
    return ShareRow(r.id, r.owner_id, r.look_id, r.revision_id, r.audience, r.caption, r.created_at, r.revoked_at,
                    r.moderation_state)


class SqlSocialRepository:
    def __init__(self, conn: Connection):
        self.conn = conn

    # ------------------------------------------------------------------ shares
    def insert_share(self, row):
        self.conn.execute(insert(S).values(id=row.id, owner_id=row.owner_id, look_id=row.look_id,
                                           revision_id=row.revision_id, audience=row.audience, caption=row.caption,
                                           created_at=row.created_at))

    def share(self, share_id, lock=False):
        q = select(S).where(S.c.id == share_id)
        r = self.conn.execute(q.with_for_update() if lock else q).one_or_none()
        return _share(r) if r else None

    def update_share(self, share_id, values):
        self.conn.execute(update(S).where(S.c.id == share_id).values(**values))

    def shares_of(self, owner_id, *, active_only, limit):
        q = select(S).where(S.c.owner_id == owner_id)
        if active_only:
            q = q.where(S.c.revoked_at.is_(None))
        return [_share(r) for r in self.conn.execute(q.order_by(S.c.created_at.desc(), S.c.id.desc()).limit(limit))]

    def count_active(self, owner_id):
        return self.conn.execute(select(func.count()).select_from(S).where(S.c.owner_id == owner_id,
                                                                            S.c.revoked_at.is_(None))).scalar_one()

    def shares_by_owners(self, owner_ids, after, limit, since=None):
        if not owner_ids:
            return []
        q = select(S).where(S.c.owner_id.in_(list(owner_ids)), S.c.revoked_at.is_(None))
        if since is not None:
            q = q.where(S.c.created_at >= since)
        if after is not None:
            q = q.where(tuple_(S.c.created_at, S.c.id) < tuple_(after.created_at, after.id))
        return [_share(r) for r in self.conn.execute(q.order_by(S.c.created_at.desc(), S.c.id.desc()).limit(limit))]

    # ------------------------------------------------------------------ settings / markers / showcase
    def plan_setting(self, user_id):
        return self.conn.execute(select(plan_share_setting.c.audience)
                                 .where(plan_share_setting.c.user_id == user_id)).scalar_one_or_none() or "none"

    def set_plan_setting(self, user_id, audience, now):
        stmt = pg_insert(plan_share_setting).values(user_id=user_id, audience=audience, updated_at=now)
        self.conn.execute(stmt.on_conflict_do_update(index_elements=["user_id"],
                                                     set_={"audience": audience, "updated_at": now}))

    def read_through(self, user_id):
        return self.conn.execute(select(notification_state.c.read_through)
                                 .where(notification_state.c.user_id == user_id)).scalar_one_or_none()

    def set_read_through(self, user_id, at):
        stmt = pg_insert(notification_state).values(user_id=user_id, read_through=at)
        self.conn.execute(stmt.on_conflict_do_update(index_elements=["user_id"], set_={"read_through": at}))

    def showcase(self, user_id):
        r = self.conn.execute(select(profile_showcase).where(profile_showcase.c.user_id == user_id)).one_or_none()
        return {"headline": r.headline, "accent": r.accent, "featured": list(r.featured)} if r else None

    def put_showcase(self, user_id, headline, accent, featured, now):
        stmt = pg_insert(profile_showcase).values(user_id=user_id, headline=headline, accent=accent,
                                                  featured=featured, updated_at=now)
        self.conn.execute(stmt.on_conflict_do_update(index_elements=["user_id"], set_={
            "headline": headline, "accent": accent, "featured": featured, "updated_at": now}))

    def erase_all(self, user_id):
        own = select(S.c.id).where(S.c.owner_id == user_id)
        self.conn.execute(delete(share_report).where((share_report.c.reporter_id == user_id)
                                                     | share_report.c.share_id.in_(own)))
        self.conn.execute(delete(inspiration).where(inspiration.c.user_id == user_id))
        for t in (profile_showcase, notification_state, plan_share_setting):
            self.conn.execute(delete(t).where(t.c.user_id == user_id))
        self.conn.execute(delete(S).where(S.c.owner_id == user_id))


    # ------------------------------------------------------------------ moderation (complete-wearhouse-tdd)
    def add_report(self, report_id, share_id, reporter_id, reason, now) -> bool:
        r = self.conn.execute(pg_insert(share_report).values(id=report_id, share_id=share_id, reporter_id=reporter_id,
                                                             reason=reason, created_at=now)
                              .on_conflict_do_nothing().returning(share_report.c.id)).first()
        return r is not None

    def open_reports(self, limit):
        n = func.count().label("n")
        rows = self.conn.execute(select(share_report.c.share_id, n, func.array_agg(share_report.c.reason).label("reasons"),
                                        func.min(share_report.c.created_at).label("first"))
                                 .where(share_report.c.status == "open").group_by(share_report.c.share_id)
                                 .order_by(func.min(share_report.c.created_at)).limit(limit)).all()
        return [{"share_id": r.share_id, "reports": r.n, "reasons": list(r.reasons), "first_reported_at": r.first}
                for r in rows]

    def resolve_reports(self, share_id, status, now):
        self.conn.execute(update(share_report).where(share_report.c.share_id == share_id,
                                                     share_report.c.status == "open")
                          .values(status=status, resolved_at=now))

    def set_moderation(self, share_id, state, actor, reason, now):
        self.conn.execute(update(S).where(S.c.id == share_id).values(moderation_state=state, moderated_by=actor,
                                                                     moderated_at=now, moderation_reason=reason))

    def reports_by(self, user_id):
        rows = self.conn.execute(select(share_report).where(share_report.c.reporter_id == user_id))
        return [{"share_id": str(r.share_id), "reason": r.reason, "status": r.status, "created_at": r.created_at.isoformat()}
                for r in rows]

    # ------------------------------------------------------------------ inspiration
    def add_inspiration(self, inspiration_id, user_id, share_id, snapshot, now):
        self.conn.execute(insert(inspiration).values(id=inspiration_id, user_id=user_id, source_share_id=share_id,
                                                     snapshot=snapshot, created_at=now))

    def inspirations(self, user_id):
        rows = self.conn.execute(select(inspiration).where(inspiration.c.user_id == user_id)
                                 .order_by(inspiration.c.created_at.desc(), inspiration.c.id))
        return [dict(r._mapping) for r in rows]

    def delete_inspiration(self, user_id, inspiration_id) -> bool:
        return self.conn.execute(delete(inspiration).where(inspiration.c.user_id == user_id,
                                                           inspiration.c.id == inspiration_id)).rowcount == 1
