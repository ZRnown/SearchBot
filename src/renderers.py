from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

from babel.dates import format_datetime
from pytz import timezone

from .config import settings


def format_channel_id_for_link(channel_id: int) -> str:
    """将 Telegram 频道 ID 格式化为链接格式（去掉 -100 前缀）"""
    channel_str = str(abs(channel_id))
    if channel_str.startswith("100"):
        return channel_str[3:]  # 去掉 "100" 前缀
    return channel_str


@dataclass
class ResourceView:
    id: str
    title: str
    type: str
    is_vip: bool
    jump_url: str | None
    preview_msg_id: int | None
    preview_url: str | None = None


CATEGORY_ICONS = {
    "novel": "📚 小说",
    "audio": "🎧 音频",
    "comic": "💖 漫画",
    "all": "🔎 全部",
}


def render_stats(counts: dict[str, int]) -> str:
    parts = []
    for category in ("novel", "audio", "comic", "all"):
        label = CATEGORY_ICONS.get(category, category)
        value = counts.get(category, 0)
        parts.append(f"{label}: {value}")
    return " | ".join(parts)


def render_result_list(
    resources: Iterable[ResourceView],
    page_index: int,
    page_size: int,
    preview_channel_id: int,
) -> str:
    lines = []
    start_number = (page_index - 1) * page_size + 1
    for idx, resource in enumerate(resources, start=start_number):
        vip_prefix = "❤️ " if resource.is_vip else ""
        category_icon = CATEGORY_ICONS.get(resource.type, "📁").split()[0]
        if resource.type in ("novel", "audio") and resource.jump_url:
            link = resource.jump_url
        else:
            if resource.preview_url:
                link = resource.preview_url
            else:
                preview_id = resource.preview_msg_id or 0
                formatted_id = format_channel_id_for_link(preview_channel_id)
                link = f"https://t.me/c/{formatted_id}/{preview_id}"
        title = (
            f'{vip_prefix}[{category_icon}] '
            f'<a href="{link}">{resource.title}</a>'
        )
        lines.append(f"{idx}. {title}")
    return "\n".join(lines) if lines else "暂无匹配条目，尝试其他关键词。"


def render_search_message(
    *,
    first_name: str,
    keyword: str,
    counts: dict[str, int],
    resources: Iterable[ResourceView],
    page_index: int,
    total_pages: int,
    reference_time: datetime,
) -> str:
    tz = timezone(settings.timezone)
    ts = format_datetime(reference_time.astimezone(tz), format="yyyy-MM-dd HH:mm:ss", locale="zh_CN")
    header = (
        f"👤 来自：{first_name}\n"
        f"🔍 关键词：「{keyword}」\n\n"
        f"📊 命中\n{render_stats(counts)}\n\n"
    )
    list_section = render_result_list(
        resources=resources,
        page_index=page_index,
        page_size=settings.bot.page_size,
        preview_channel_id=settings.channels.comic_preview_channel_id,
    )
    footer = f"\n\n第 {page_index} / {max(total_pages,1)} 页 | 更新时间 {ts}"
    return header + list_section + footer

