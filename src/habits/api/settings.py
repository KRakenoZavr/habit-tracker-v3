"""Settings loaded from the environment."""

import os
from dataclasses import dataclass
from zoneinfo import ZoneInfo


@dataclass(frozen=True, slots=True)
class Settings:
    database_url: str = "sqlite:///./habits.db"
    timezone: str = "UTC"

    @classmethod
    def from_env(cls) -> "Settings":
        defaults = cls()
        database_url = os.environ.get("HABITS_DATABASE_URL", defaults.database_url)
        timezone = os.environ.get("HABITS_TIMEZONE", defaults.timezone)
        try:
            ZoneInfo(timezone)
        except Exception as exc:
            raise ValueError(f"invalid timezone: {timezone!r}") from exc
        return cls(database_url=database_url, timezone=timezone)
