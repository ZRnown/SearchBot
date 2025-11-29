from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import List

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class ChannelConfig:
    search_channel_id: int
    comic_preview_channel_id: int
    storage_channel_id: int


@dataclass(frozen=True)
class BotConfig:
    page_size: int


@dataclass(frozen=True)
class DatabaseConfig:
    url: str


@dataclass(frozen=True)
class Settings:
    bot_token: str
    admin_ids: list[int]
    channels: ChannelConfig
    bot: BotConfig
    database: DatabaseConfig
    web_port: int
    web_admin_user: str
    web_admin_pass: str
    security: "SecurityConfig"
    vip_recharge_url: str
    timezone: str = "Asia/Shanghai"


@dataclass(frozen=True)
class SecurityConfig:
    jwt_secret: str
    token_expire_minutes: int


def parse_int(value: str, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def parse_int_list(raw: str | None) -> list[int]:
    if not raw:
        return []
    values: List[int] = []
    for token in raw.split(","):
        token = token.strip()
        if not token:
            continue
        try:
            values.append(int(token))
        except ValueError:
            continue
    return values


def read_env_file(path: str | None = None) -> Settings:
    base_dir = Path(path or os.getcwd())
    return Settings(
        bot_token=os.environ["BOT_TOKEN"],
        admin_ids=parse_int_list(os.environ.get("ADMIN_IDS")),
        channels=ChannelConfig(
            search_channel_id=parse_int(
                os.environ.get("SEARCH_CHANNEL_ID", "0"), default=0
            ),
            comic_preview_channel_id=parse_int(
                os.environ.get("COMIC_PREVIEW_CHANNEL_ID", "0"), default=0
            ),
            storage_channel_id=parse_int(
                os.environ.get("STORAGE_CHANNEL_ID", "0"), default=0
            ),
        ),
        bot=BotConfig(
            page_size=parse_int(os.environ.get("PAGE_SIZE", "5"), default=5),
        ),
        database=DatabaseConfig(
            url=os.environ.get(
                "DATABASE_URL",
                "mysql+pymysql://searchbot:searchbot@localhost:3306/searchbot",
            )
        ),
        web_port=parse_int(os.environ.get("WEB_PORT", "8080"), default=8080),
        web_admin_user=os.environ.get("WEB_ADMIN_USER", "admin"),
        web_admin_pass=os.environ.get("WEB_ADMIN_PASS", "admin123"),
        security=SecurityConfig(
            jwt_secret=os.environ.get("ADMIN_JWT_SECRET", "change-me"),
            token_expire_minutes=parse_int(
                os.environ.get("ADMIN_TOKEN_EXPIRE_MINUTES", "60"), default=60
            ),
        ),
        vip_recharge_url=os.environ.get("VIP_RECHARGE_URL", "https://t.me/your_bot"),
        timezone=os.environ.get("TIMEZONE", "Asia/Shanghai"),
    )


settings = read_env_file()

