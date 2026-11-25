from __future__ import annotations

from sqlalchemy import text, delete, insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Connection

from ...platform.ids import new_id
from .tables import app_user, role_grant, user_subject


class SqlIdentityRepository:
    def __init__(self, conn: Connection):
        self.conn = conn

    def find(self, issuer, subject):
        return self.conn.execute(select(user_subject.c.user_id).where(
            user_subject.c.issuer == issuer, user_subject.c.subject == subject)).scalar_one_or_none()

    def resolve(self, issuer, subject, now):
        existing = self.find(issuer, subject)
        if existing is not None:
            return existing, False
        candidate = new_id()
        sp = self.conn.begin_nested()  # undo the user row if another request wins the subject mapping
        self.conn.execute(insert(app_user).values(id=candidate, created_at=now))
        won = self.conn.execute(pg_insert(user_subject)
                                .values(issuer=issuer, subject=subject, user_id=candidate, created_at=now)
                                .on_conflict_do_nothing(index_elements=["issuer", "subject"])
                                .returning(user_subject.c.user_id)).scalar_one_or_none()
        if won is None:
            sp.rollback()
            return self.find(issuer, subject), False
        sp.commit()
        return candidate, True

    def roles(self, user_id):
        return frozenset(self.conn.execute(select(role_grant.c.role).where(role_grant.c.user_id == user_id)).scalars())

    def grant(self, user_id, role, granted_by, now):
        r = self.conn.execute(pg_insert(role_grant).values(user_id=user_id, role=role, granted_by=granted_by,
                                                           granted_at=now)
                              .on_conflict_do_nothing().returning(role_grant.c.role)).scalar_one_or_none()
        return r is not None

    def staff(self):
        out: dict = {}
        for user_id, role in self.conn.execute(select(role_grant.c.user_id, role_grant.c.role)
                                               .order_by(role_grant.c.user_id, role_grant.c.role)).all():
            out.setdefault(user_id, set()).add(role)
        return {k: frozenset(v) for k, v in out.items()}

    def lock_admins(self):
        # A transaction-scoped advisory lock serialises admin revocations without needing UPDATE on role_grant
        # (SELECT ... FOR UPDATE would; the runtime role deliberately has no UPDATE there).
        self.conn.execute(text("SELECT pg_advisory_xact_lock(hashtext('wearhouse.role_grant.admin'))"))
        return list(self.conn.execute(select(role_grant.c.user_id).where(role_grant.c.role == "admin")
                                      .order_by(role_grant.c.user_id)).scalars())

    def revoke(self, user_id, role):
        return self.conn.execute(delete(role_grant).where(role_grant.c.user_id == user_id,
                                                          role_grant.c.role == role)).rowcount > 0

    def tokens_not_before(self, user_id):
        return self.conn.execute(select(app_user.c.tokens_not_before).where(app_user.c.id == user_id)).scalar()


class SqlAccountDirectory:
    def __init__(self, conn: Connection):
        self.conn = conn

    def lock(self, user_id):
        r = self.conn.execute(select(app_user.c.created_at).where(app_user.c.id == user_id,
                                                                  app_user.c.deleted_at.is_(None))
                              .with_for_update()).one_or_none()
        return {"created_at": r.created_at} if r else None

    def timeline(self, user_id):
        r = self.conn.execute(select(app_user.c.created_at, app_user.c.tokens_not_before)
                              .where(app_user.c.id == user_id, app_user.c.deleted_at.is_(None))).one_or_none()
        return {"created_at": r.created_at, "tokens_not_before": r.tokens_not_before} if r else None

    def revoke_tokens(self, user_id, now):
        self.conn.execute(update(app_user).where(app_user.c.id == user_id).values(tokens_not_before=now))

    def tombstone(self, user_id, now):
        self.conn.execute(delete(user_subject).where(user_subject.c.user_id == user_id))
        self.conn.execute(delete(role_grant).where(role_grant.c.user_id == user_id))
        self.conn.execute(update(app_user).where(app_user.c.id == user_id)
                          .values(deleted_at=now, display_name=None, tokens_not_before=now))


class SqlUserDirectory:
    """Identity's read interface for other modules (ownership checks an audience user exists)."""

    def __init__(self, conn: Connection):
        self.conn = conn

    def exists(self, user_id) -> bool:
        return self.conn.execute(select(app_user.c.id).where(app_user.c.id == user_id)).first() is not None
