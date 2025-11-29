from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

CATEGORY_BUTTONS = [
    ("novel", "📚小说"),
    ("audio", "🎧音频"),
    ("comic", "💖漫画"),
    ("all", "🔎全部"),
]


def build_filter_row(active_filter: str, keyword: str, page: int) -> list[InlineKeyboardButton]:
    buttons: list[InlineKeyboardButton] = []
    for value, label in CATEGORY_BUTTONS:
        display = f"✅{label[1:]}" if active_filter == value else label
        payload = {"a": "filter", "f": value, "k": keyword, "p": 1}
        buttons.append(
            InlineKeyboardButton(
                text=display,
                callback_data=json_dumps(payload),
            )
        )
    return buttons


def build_pagination_row(keyword: str, active_filter: str, page: int) -> list[InlineKeyboardButton]:
    prev_payload = {"a": "page", "dir": "prev", "k": keyword, "f": active_filter, "p": page - 1}
    next_payload = {"a": "page", "dir": "next", "k": keyword, "f": active_filter, "p": page + 1}
    return [
        InlineKeyboardButton(text="« 上一页", callback_data=json_dumps(prev_payload)),
        InlineKeyboardButton(text="下一页 »", callback_data=json_dumps(next_payload)),
    ]


def build_ads_rows(ad_slots: list[tuple[str, str]]) -> list[list[InlineKeyboardButton]]:
    rows: list[list[InlineKeyboardButton]] = []
    for idx in range(0, len(ad_slots), 2):
        row_buttons: list[InlineKeyboardButton] = []
        for text, url in ad_slots[idx : idx + 2]:
            row_buttons.append(InlineKeyboardButton(text=text, url=url))
        if row_buttons:
            rows.append(row_buttons)
    return rows


def build_keyboard(*, keyword: str, active_filter: str, page: int, ads: list[tuple[str, str]]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        build_filter_row(active_filter, keyword, page),
        build_pagination_row(keyword, active_filter, page),
    ]
    rows.extend(build_ads_rows(ads))
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_comic_nav_keyboard(resource_id: str, page: int, total_pages: int) -> InlineKeyboardMarkup:
    buttons: list[InlineKeyboardButton] = []
    if page > 1:
        buttons.append(
            InlineKeyboardButton(
                text="⬅️ 上一页",
                callback_data=json_dumps(
                    {"a": "comic_nav", "rid": resource_id, "p": page - 1}
                ),
            )
        )
    buttons.append(
        InlineKeyboardButton(
            text=f"{page} / {total_pages} 页",
            callback_data=json_dumps({"a": "noop"}),
        )
    )
    if page < total_pages:
        buttons.append(
            InlineKeyboardButton(
                text="下一页 ➡️",
                callback_data=json_dumps(
                    {"a": "comic_nav", "rid": resource_id, "p": page + 1}
                ),
            )
        )
    return InlineKeyboardMarkup(inline_keyboard=[buttons])


# JSON helpers with short base64-like encoding to stay under 64 bytes
import json


def json_dumps(payload: dict) -> str:
    return json.dumps(payload, separators=(",", ":"))

