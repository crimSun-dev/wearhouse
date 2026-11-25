from __future__ import annotations

from sqlalchemy import insert, select, update
from sqlalchemy.engine import Connection

from .tables import item_neighbour, recommendation_artifact

A = recommendation_artifact


class SqlArtifactRepository:
    def __init__(self, conn: Connection):
        self.conn = conn

    def active(self, kind):
        r = self.conn.execute(select(A).where(A.c.kind == kind, A.c.active.is_(True))).one_or_none()
        return dict(r._mapping) if r else None

    def all(self):
        return [dict(r._mapping) for r in self.conn.execute(select(A).order_by(A.c.imported_at.desc()))]

    def create(self, *, artifact_id, kind, name, version, mode, model_hash, manifest, imported_by, now):
        self.conn.execute(insert(A).values(id=artifact_id, kind=kind, name=name, version=version, mode=mode,
                                           model_hash=model_hash, manifest=manifest, active=False,
                                           imported_by=imported_by, imported_at=now))

    def add_neighbours(self, rows):
        for i in range(0, len(rows), 5000):
            self.conn.execute(insert(item_neighbour), rows[i:i + 5000])

    def activate(self, artifact_id, kind):
        self.conn.execute(update(A).where(A.c.kind == kind, A.c.active.is_(True)).values(active=False))
        self.conn.execute(update(A).where(A.c.id == artifact_id).values(active=True))

    def neighbours(self, artifact_id, product_id, limit):
        rows = self.conn.execute(select(item_neighbour.c.neighbour_id).where(
            item_neighbour.c.artifact_id == artifact_id, item_neighbour.c.product_id == product_id)
            .order_by(item_neighbour.c.rank).limit(limit))
        return list(rows.scalars())
