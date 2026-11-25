from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Connection

from ..application import feed_from_json
from .tables import user_weather_location, weather_cache


class SqlWeatherRepository:
    def __init__(self, conn: Connection):
        self.conn = conn

    def get_cache(self, adm4):
        r = self.conn.execute(select(weather_cache).where(weather_cache.c.adm4 == adm4)).one_or_none()
        if r is None:
            return None
        return feed_from_json({"slots": r.slots, "fetched_at": r.fetched_at.isoformat(),
                               "fresh_until": r.fresh_until.isoformat()})

    def put_cache(self, adm4, feed):
        slots = [{"at": s.at.isoformat(), "temp_c": s.temp_c, "humidity": s.humidity, "description": s.description,
                  "rain": s.rain, "hot": s.hot} for s in feed.slots]
        stmt = pg_insert(weather_cache).values(adm4=adm4, slots=slots, fetched_at=feed.fetched_at,
                                               fresh_until=feed.fresh_until)
        self.conn.execute(stmt.on_conflict_do_update(index_elements=["adm4"], set_={
            "slots": slots, "fetched_at": feed.fetched_at, "fresh_until": feed.fresh_until}))

    def get_location(self, user_id):
        return self.conn.execute(select(user_weather_location.c.adm4)
                                 .where(user_weather_location.c.user_id == user_id)).scalar_one_or_none()

    def set_location(self, user_id, adm4, now):
        stmt = pg_insert(user_weather_location).values(user_id=user_id, adm4=adm4, updated_at=now)
        self.conn.execute(stmt.on_conflict_do_update(index_elements=["user_id"], set_={"adm4": adm4, "updated_at": now}))

    def clear_location(self, user_id):
        self.conn.execute(delete(user_weather_location).where(user_weather_location.c.user_id == user_id))
