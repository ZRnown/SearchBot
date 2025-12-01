from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

CATEGORY_BUTTONS = [
    ("novel", "📚小说"),
    ("audio", "🎧音频"),
    ("comic", "💖漫画"),
    ("all", "🔎全部"),
]


def build_filter_row(active_filter: str, keyword: str, page: int, user_id: int) -> list[InlineKeyboardButton]:
    buttons: list[InlineKeyboardButton] = []
    for value, label in CATEGORY_BUTTONS:
        display = f"✅{label[1:]}" if active_filter == value else label
        payload = {"a": "filter", "f": value, "k": keyword, "p": 1, "u": user_id}
        buttons.append(
            InlineKeyboardButton(
                text=display,
                callback_data=json_dumps(payload),
            )
        )
    return buttons


def build_pagination_row(keyword: str, active_filter: str, page: int, total_pages: int, user_id: int) -> list[InlineKeyboardButton]:
    # 始终显示两个按钮，即使只有一页
    buttons: list[InlineKeyboardButton] = []
    
    # 上一页按钮（始终显示，但在第一页时禁用）
    if page > 1:
        prev_payload = {"a": "page", "dir": "prev", "k": keyword, "f": active_filter, "p": page - 1, "u": user_id}
        buttons.append(InlineKeyboardButton(text="« 上一页", callback_data=json_dumps(prev_payload)))
    else:
        # 第一页时显示禁用状态的按钮
        buttons.append(InlineKeyboardButton(text="« 上一页", callback_data=json_dumps({"a": "noop"})))
    
    # 下一页按钮（始终显示，但在最后一页时禁用）
    if page < total_pages:
        next_payload = {"a": "page", "dir": "next", "k": keyword, "f": active_filter, "p": page + 1, "u": user_id}
        buttons.append(InlineKeyboardButton(text="下一页 »", callback_data=json_dumps(next_payload)))
    else:
        # 最后一页时显示禁用状态的按钮
        buttons.append(InlineKeyboardButton(text="下一页 »", callback_data=json_dumps({"a": "noop"})))
    
    return buttons


def build_ads_rows(ad_slots: list[tuple[str, str]]) -> list[list[InlineKeyboardButton]]:
    rows: list[list[InlineKeyboardButton]] = []
    for idx in range(0, len(ad_slots), 2):
        row_buttons: list[InlineKeyboardButton] = []
        for text, url in ad_slots[idx : idx + 2]:
            row_buttons.append(InlineKeyboardButton(text=text, url=url))
        if row_buttons:
            rows.append(row_buttons)
    return rows


def build_keyboard(*, keyword: str, active_filter: str, page: int, total_pages: int, user_id: int, ads: list[tuple[str, str]]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        build_filter_row(active_filter, keyword, page, user_id),
    ]
    
    # 始终添加分页行（即使只有一页也显示）
    pagination_row = build_pagination_row(keyword, active_filter, page, total_pages, user_id)
    rows.append(pagination_row)
    
    rows.extend(build_ads_rows(ads))
    
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_comic_nav_keyboard(resource_id: str, page: int, total_pages: int) -> InlineKeyboardMarkup:
    buttons: list[InlineKeyboardButton] = []
    if page > 1:
        buttons.append(
            InlineKeyboardButton(
                text="⬅️ 上一页",
                callback_data=json_dumps(
                    {"a": "cn", "r": resource_id, "p": page - 1}
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
                    {"a": "cn", "r": resource_id, "p": page + 1}
                ),
            )
        )
    return InlineKeyboardMarkup(inline_keyboard=[buttons])


# JSON helpers with short base64-like encoding to stay under 64 bytes
import json


def json_dumps(payload: dict) -> str:
    """将 payload 序列化为 JSON 字符串，确保不超过 64 字节限制"""
    result = json.dumps(payload, separators=(",", ":"))
    result_bytes = result.encode('utf-8')
    result_len = len(result_bytes)
    
    # Telegram 限制 callback_data 为 64 字节
    if result_len > 64:
        # 对于 comic_nav 操作（使用 "cn" 作为 action），resource_id 是必需的，不能截断
        # 但我们可以使用更短的字段名（已经在 build_comic_nav_keyboard 中使用 "r" 而不是 "rid"）
        if payload.get("a") in ("comic_nav", "cn"):
            # comic_nav 的 payload 格式: {"a":"cn","r":"uuid","p":1}
            # UUID 是 36 字符，加上其他字段，最小长度约为: 3+1+36+1+1+1 = 43 字节
            # 如果还是超过，说明 UUID 格式有问题，记录警告
            if result_len > 64:
                print(f"[Keyboards] ⚠️ comic_nav callback_data 超过 64 字节: {result_len} 字节, payload: {payload}")
                # 对于 comic_nav，我们不能截断 resource_id，所以如果超过限制，返回错误提示
                # 但实际上，使用 "r" 字段名和 "cn" action 后，应该不会超过 64 字节
                # 如果还是超过，可能是 UUID 格式异常，记录警告但继续
                pass
        
        # 如果超过限制，尝试截断 keyword
        if "k" in payload and payload["k"]:
            keyword = payload["k"]
            # 计算其他字段的长度（不包含 keyword）
            other_payload = {k: v for k, v in payload.items() if k != "k"}
            other_json = json.dumps(other_payload, separators=(",", ":"))
            other_len = len(other_json.encode('utf-8'))
            
            # 计算可以用于 keyword 的最大长度
            # 需要预留空间给 "k":"" 和可能的逗号
            max_keyword_bytes = 64 - other_len - 8  # 预留空间
            
            if max_keyword_bytes > 0:
                # 截断 keyword
                keyword_bytes = keyword.encode('utf-8')
                if len(keyword_bytes) > max_keyword_bytes:
                    # 按字节截断，确保不会截断 UTF-8 字符
                    truncated = keyword_bytes[:max_keyword_bytes]
                    # 找到最后一个完整的 UTF-8 字符
                    while truncated and (truncated[-1] & 0xC0) == 0x80:
                        truncated = truncated[:-1]
                    payload["k"] = truncated.decode('utf-8', errors='ignore')
                # 重新序列化
                result = json.dumps(payload, separators=(",", ":"))
                result_bytes = result.encode('utf-8')
                result_len = len(result_bytes)
            else:
                # 如果其他字段已经超过限制，移除 keyword
                payload.pop("k", None)
                result = json.dumps(payload, separators=(",", ":"))
                result_bytes = result.encode('utf-8')
                result_len = len(result_bytes)
        
        # 最终检查：如果还是超过 64 字节，使用最小格式
        if result_len > 64:
            # 对于 comic_nav，不能使用最小格式（会丢失 resource_id）
            if payload.get("a") in ("comic_nav", "cn"):
                print(f"[Keyboards] ❌ comic_nav callback_data 仍然超过 64 字节: {result_len} 字节")
                # 返回原始结果，让 Telegram 处理（可能会失败，但至少不会丢失数据）
                return result
            
            # 使用最短格式：只保留必要的字段
            minimal_payload = {
                "a": payload.get("a", ""),
                "f": payload.get("f", "all"),
                "p": payload.get("p", 1),
                "u": payload.get("u", 0),
            }
            # 如果 keyword 很短，尝试添加（最多 15 个字符）
            if "k" in payload and payload["k"]:
                test_payload = minimal_payload.copy()
                test_payload["k"] = payload["k"][:15]  # 最多 15 个字符
                test_result = json.dumps(test_payload, separators=(",", ":"))
                if len(test_result.encode('utf-8')) <= 64:
                    result = test_result
                else:
                    result = json.dumps(minimal_payload, separators=(",", ":"))
            else:
                result = json.dumps(minimal_payload, separators=(",", ":"))
            
            result_bytes = result.encode('utf-8')
            result_len = len(result_bytes)
            
            # 如果还是超过，记录警告
            if result_len > 64:
                print(f"[Keyboards] ⚠️ callback_data 仍然超过 64 字节: {result_len} 字节, payload: {payload}")
                # 强制截断到 64 字节（不推荐，但作为最后手段）
                result = result_bytes[:64].decode('utf-8', errors='ignore')
    
    return result

