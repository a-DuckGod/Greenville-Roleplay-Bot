from __future__ import annotations

import datetime
import json
import os
import sqlite3
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import config


@dataclass
class GuildConfig:
    guild_id: int
    prefix: str = config.PREFIX
    rules_channel_id: int | None = None
    session_channel_id: int | None = None
    staff_role_ids: list[int] = field(default_factory=list)
    ea_role_ids: list[int] = field(default_factory=list)
    booster_role_id: int | None = None
    startup_ping: str = "everyone"  # "everyone", "here", "none", or "role:<id>"
    release_ping: str = "everyone"  # "everyone", "here", "none", or "role:<id>"
    required_reactions: int = 5
    startup_emojis: list[str] = field(default_factory=lambda: list(config.EMOJI_LIST))

    def format_ping(self, mode: str) -> str | None:
        if mode == "everyone":
            return "@everyone"
        if mode == "here":
            return "@here"
        if mode == "none" or not mode:
            return None
        if mode.startswith("role:"):
            role_id = mode.split(":", 1)[1]
            if role_id.isdigit():
                return f"<@&{role_id}>"
        return None


class Database:
    def __init__(self, db_path: str | None = None) -> None:
        resolved = db_path or os.environ.get("DATABASE_PATH") or "data/bot.db"
        self.db_path = resolved
        self._lock = threading.Lock()
        self._guild_cache: dict[int, GuildConfig] = {}

        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self.init_db()

    def init_db(self) -> None:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS guild_configs (
                    guild_id INTEGER PRIMARY KEY,
                    prefix TEXT NOT NULL DEFAULT '-',
                    rules_channel_id INTEGER,
                    session_channel_id INTEGER,
                    staff_role_ids TEXT NOT NULL DEFAULT '[]',
                    ea_role_ids TEXT NOT NULL DEFAULT '[]',
                    booster_role_id INTEGER,
                    startup_ping TEXT NOT NULL DEFAULT 'everyone',
                    release_ping TEXT NOT NULL DEFAULT 'everyone',
                    required_reactions INTEGER NOT NULL DEFAULT 5,
                    startup_emojis TEXT
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS session_links (
                    message_id INTEGER PRIMARY KEY,
                    guild_id INTEGER NOT NULL,
                    link_type TEXT NOT NULL,
                    url TEXT NOT NULL,
                    host_id INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    @staticmethod
    def _parse_int_list(raw: str | None) -> list[int]:
        if not raw:
            return []
        try:
            data = json.loads(raw)
            return [int(x) for x in data if isinstance(x, int) or (isinstance(x, str) and x.isdigit())]
        except (json.JSONDecodeError, TypeError, ValueError):
            return []

    @staticmethod
    def _parse_str_list(raw: str | None) -> list[str]:
        if not raw:
            return list(config.EMOJI_LIST)
        try:
            data = json.loads(raw)
            parsed = [str(x) for x in data if str(x).strip()]
            return parsed or list(config.EMOJI_LIST)
        except (json.JSONDecodeError, TypeError, ValueError):
            return list(config.EMOJI_LIST)

    def get_guild_config(self, guild_id: int) -> GuildConfig:
        if guild_id in self._guild_cache:
            return self._guild_cache[guild_id]

        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT * FROM guild_configs WHERE guild_id = ?", (guild_id,))
            row = cur.fetchone()

        if row is None:
            cfg = GuildConfig(guild_id=guild_id)
        else:
            cfg = GuildConfig(
                guild_id=row["guild_id"],
                prefix=row["prefix"] or config.PREFIX,
                rules_channel_id=row["rules_channel_id"],
                session_channel_id=row["session_channel_id"],
                staff_role_ids=self._parse_int_list(row["staff_role_ids"]),
                ea_role_ids=self._parse_int_list(row["ea_role_ids"]),
                booster_role_id=row["booster_role_id"],
                startup_ping=row["startup_ping"] or "everyone",
                release_ping=row["release_ping"] or "everyone",
                required_reactions=int(row["required_reactions"] or 5),
                startup_emojis=self._parse_str_list(row["startup_emojis"]),
            )

        self._guild_cache[guild_id] = cfg
        return cfg

    def save_guild_config(self, cfg: GuildConfig) -> GuildConfig:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                """
                INSERT INTO guild_configs (
                    guild_id, prefix, rules_channel_id, session_channel_id,
                    staff_role_ids, ea_role_ids, booster_role_id,
                    startup_ping, release_ping, required_reactions, startup_emojis
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET
                    prefix = excluded.prefix,
                    rules_channel_id = excluded.rules_channel_id,
                    session_channel_id = excluded.session_channel_id,
                    staff_role_ids = excluded.staff_role_ids,
                    ea_role_ids = excluded.ea_role_ids,
                    booster_role_id = excluded.booster_role_id,
                    startup_ping = excluded.startup_ping,
                    release_ping = excluded.release_ping,
                    required_reactions = excluded.required_reactions,
                    startup_emojis = excluded.startup_emojis
                """,
                (
                    cfg.guild_id,
                    cfg.prefix,
                    cfg.rules_channel_id,
                    cfg.session_channel_id,
                    json.dumps(cfg.staff_role_ids),
                    json.dumps(cfg.ea_role_ids),
                    cfg.booster_role_id,
                    cfg.startup_ping,
                    cfg.release_ping,
                    cfg.required_reactions,
                    json.dumps(cfg.startup_emojis),
                ),
            )
            self._conn.commit()
        self._guild_cache[cfg.guild_id] = cfg
        return cfg

    def update_guild_config(self, guild_id: int, **updates: Any) -> GuildConfig:
        cfg = self.get_guild_config(guild_id)
        for key, value in updates.items():
            if hasattr(cfg, key):
                setattr(cfg, key, value)
        return self.save_guild_config(cfg)

    def reset_guild_config(self, guild_id: int) -> GuildConfig:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("DELETE FROM guild_configs WHERE guild_id = ?", (guild_id,))
            self._conn.commit()
        self._guild_cache.pop(guild_id, None)
        return self.get_guild_config(guild_id)

    def save_session_link(
        self,
        message_id: int,
        guild_id: int,
        link_type: str,
        url: str,
        host_id: int,
    ) -> None:
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                """
                INSERT INTO session_links (message_id, guild_id, link_type, url, host_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(message_id) DO UPDATE SET
                    link_type = excluded.link_type,
                    url = excluded.url,
                    host_id = excluded.host_id,
                    created_at = excluded.created_at
                """,
                (message_id, guild_id, link_type, url, host_id, now),
            )
            self._conn.commit()

    def get_session_link(self, message_id: int) -> dict[str, Any] | None:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT * FROM session_links WHERE message_id = ?", (message_id,))
            row = cur.fetchone()
        if row is None:
            return None
        return dict(row)
