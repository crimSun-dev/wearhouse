"""Outfit recommendation runs and deduplicated feedback (align-wearhouse-outfit-recommender).
`recommended(g)` = distinct runs that displayed g; `chosen(g)` = runs whose chosen outfit contained g."""
from __future__ import annotations

from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Connection

from .tables import recommendation_choice, recommendation_exposure, recommendation_run

RUN, EXP, CHOICE = recommendation_run, recommendation_exposure, recommendation_choice


class SqlRecommendationEvents:
    def __init__(self, conn: Connection):
        self.conn = conn

    def create_run(self, *, run_id, user_id, context, suggestions, now):
        self.conn.execute(insert(RUN).values(id=run_id, user_id=user_id, context=context, suggestions=suggestions,
                                             created_at=now))

    def run(self, user_id, run_id):
        r = self.conn.execute(select(RUN).where(RUN.c.id == run_id, RUN.c.user_id == user_id)).one_or_none()
        return dict(r._mapping) if r else None

    def record_displayed(self, user_id, run_id, item_ids, now):
        if item_ids:
            self.conn.execute(pg_insert(EXP).values([{"run_id": run_id, "item_id": i, "user_id": user_id}
                                                     for i in item_ids]).on_conflict_do_nothing())
        self.conn.execute(update(RUN).where(RUN.c.id == run_id, RUN.c.displayed_at.is_(None)).values(displayed_at=now))

    def choice(self, run_id):
        r = self.conn.execute(select(CHOICE).where(CHOICE.c.run_id == run_id)).one_or_none()
        return dict(r._mapping) if r else None

    def record_choice(self, user_id, run_id, index, item_ids, now) -> bool:
        r = self.conn.execute(pg_insert(CHOICE).values(run_id=run_id, user_id=user_id, suggestion_index=index,
                                                       item_ids=list(item_ids), chosen_at=now)
                              .on_conflict_do_nothing().returning(CHOICE.c.run_id)).first()
        return r is not None

    def counts(self, user_id) -> dict:
        """item_id -> (chosen, recommended)."""
        shown = dict(self.conn.execute(select(EXP.c.item_id, func.count()).where(EXP.c.user_id == user_id)
                                       .group_by(EXP.c.item_id)).all())
        item = func.unnest(CHOICE.c.item_ids).label("item")
        sub = select(item).where(CHOICE.c.user_id == user_id).subquery()
        chosen = dict(self.conn.execute(select(sub.c.item, func.count()).group_by(sub.c.item)).all())
        return {i: (chosen.get(i, 0), shown.get(i, 0)) for i in set(shown) | set(chosen)}

    def export(self, user_id) -> dict:
        runs = self.conn.execute(select(func.count()).select_from(RUN).where(RUN.c.user_id == user_id)).scalar_one()
        choices = [{"run_id": str(r.run_id), "suggestion_index": r.suggestion_index,
                    "item_ids": [str(i) for i in r.item_ids], "chosen_at": r.chosen_at.isoformat()}
                   for r in self.conn.execute(select(CHOICE).where(CHOICE.c.user_id == user_id)
                                              .order_by(CHOICE.c.chosen_at))]
        return {"runs": runs, "choices": choices}

    def erase(self, user_id):
        self.conn.execute(delete(CHOICE).where(CHOICE.c.user_id == user_id))
        self.conn.execute(delete(EXP).where(EXP.c.user_id == user_id))
        self.conn.execute(delete(RUN).where(RUN.c.user_id == user_id))
