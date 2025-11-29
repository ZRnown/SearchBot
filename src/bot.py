from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InputMediaPhoto, Message, User as TelegramUser

from .config import settings
from .db import SearchButton, User, db_session, init_db
from .keyboards import build_comic_nav_keyboard, build_keyboard
from .renderers import render_search_message
from .repositories import ResourceRepository
from .services.search_service import SearchService
from .utils import chunk_list


router = Router()
bot = Bot(
    token=settings.bot_token,
    default=DefaultBotProperties(parse_mode="HTML"),
)


@router.message(Command("start"))
async def handle_start(message: Message):
    with db_session() as session:
        ensure_user_record(session, message.from_user)
    payload = (message.text or "").split(maxsplit=1)
    if len(payload) > 1 and payload[1].startswith("comic_"):
        resource_id = payload[1].split("comic_", 1)[-1]
        if resource_id:
            await send_comic_page(
                chat_id=message.chat.id,
                user=message.from_user,
                resource_id=resource_id,
                page=1,
            )
            return
    await message.answer("请输入关键字到搜索频道，即可获取资源列表。")


@router.message(flags={"block": False})
async def track_messages(message: Message):
    if not message.from_user:
        return
    with db_session() as session:
        ensure_user_record(session, message.from_user)


@router.message(F.chat.id == settings.channels.search_channel_id, F.text)
async def handle_search(message: Message):
    keyword = message.text.strip()
    await respond_with_results(
        message=message,
        keyword=keyword,
        category="all",
        page=1,
    )


@router.callback_query()
async def handle_callback(query: CallbackQuery):
    data = query.data or ""
    try:
        payload = json.loads(data)
    except ValueError:
        await query.answer("数据异常", show_alert=True)
        return

    action = payload.get("a")
    if action in {"filter", "page"}:
        keyword = payload.get("k", "")
        category = payload.get("f", "all")
        page = max(payload.get("p", 1), 1)
        if action == "page":
            direction = payload.get("dir")
            if direction == "prev" and page < 1:
                await query.answer("已经是第一页", show_alert=False)
                return
        await respond_with_results(
            message=query.message,
            keyword=keyword,
            category=category,
            page=page,
            query=query,
        )
        return

    if action == "comic_nav":
        resource_id = payload.get("rid")
        page = max(payload.get("p", 1), 1)
        await send_comic_page(
            chat_id=query.message.chat.id,
            user=query.from_user,
            resource_id=resource_id,
            page=page,
            query=query,
        )
        return

    if action == "noop":
        await query.answer()
        return

    await query.answer("未知操作", show_alert=True)


def ensure_user_record(session, telegram_user: TelegramUser | None) -> User | None:
    if telegram_user is None:
        return None
    db_user = session.get(User, telegram_user.id)
    if not db_user:
        db_user = User(
            user_id=telegram_user.id,
            first_name=telegram_user.first_name,
            username=telegram_user.username,
        )
        session.add(db_user)
        session.flush()
    else:
        updated = False
        if telegram_user.first_name and db_user.first_name != telegram_user.first_name:
            db_user.first_name = telegram_user.first_name
            updated = True
        if telegram_user.username and db_user.username != telegram_user.username:
            db_user.username = telegram_user.username
            updated = True
        if updated:
            session.flush()
    return db_user


async def respond_with_results(
    *,
    message: Message | None,
    keyword: str,
    category: str,
    page: int,
    query: CallbackQuery | None = None,
):
    with db_session() as session:
        actor = query.from_user if query else (message.from_user if message else None)
        ensure_user_record(session, actor)
        service = SearchService(session)
        result = service.run(keyword=keyword, category=category, page=page)
        buttons = (
            session.query(SearchButton)
            .order_by(SearchButton.sort_order.asc(), SearchButton.id.asc())
            .all()
        )

    display_name = (
        (query.from_user.first_name if query else None)
        or (message.from_user.first_name if message else None)
        or "Unknown"
    )
    html = render_search_message(
        first_name=display_name,
        keyword=keyword,
        counts=result.counts,
        resources=result.rows,
        page_index=page,
        total_pages=result.total_pages,
        reference_time=datetime.utcnow(),
    )
    keyboard = build_keyboard(
        keyword=keyword,
        active_filter=category,
        page=page,
        ads=[(button.label, button.url) for button in buttons],
    )

    if query:
        await query.message.edit_text(
            html,
            parse_mode="HTML",
            reply_markup=keyboard,
        )
        await query.answer()
    else:
        await message.reply(html, parse_mode="HTML", reply_markup=keyboard)


async def send_comic_page(
    *,
    chat_id: int,
    user,
    resource_id: str,
    page: int,
    query: CallbackQuery | None = None,
):
    with db_session() as session:
        repo = ResourceRepository(session)
        resource = repo.get(resource_id)
        if not resource or resource.type != "comic":
            if query:
                await query.answer("漫画不存在", show_alert=True)
            else:
                await bot.send_message(chat_id, "漫画不存在或已下架。")
            return

        total_images = repo.count_comic_files(resource_id)
        if total_images == 0:
            await bot.send_message(chat_id, "该漫画尚未上传文件。")
            if query:
                await query.answer()
            return

        db_user = ensure_user_record(session, user)

        # 确保时区一致性
        now = datetime.now(timezone.utc)
        is_vip = False
        if db_user.vip_expiry:
            # 如果 vip_expiry 没有时区信息，添加 UTC 时区
            if db_user.vip_expiry.tzinfo is None:
                from datetime import timezone as tz
                vip_expiry = db_user.vip_expiry.replace(tzinfo=tz.utc)
            else:
                vip_expiry = db_user.vip_expiry
            is_vip = vip_expiry > now

        if not is_vip:
            recharge_url = settings.vip_recharge_url
            await bot.send_message(
                chat_id,
                f"🔒 此内容仅限 VIP 会员访问\n\n"
                f"点击下方链接开通 VIP：\n{recharge_url}",
            )
            if query:
                await query.answer("请先开通 VIP", show_alert=True)
            return

        # VIP用户：发送所有图片
        all_files = repo.list_comic_files(resource_id, limit=total_images, offset=0)
        # 每10张图片一组发送
        for chunk in chunk_list(all_files, 10):
            media_group = [InputMediaPhoto(media=item.file_id) for item in chunk]
            await bot.send_media_group(chat_id, media_group)
        
        # 发送汇总信息
        await bot.send_message(
            chat_id,
            f"{resource.title}\n"
            f"合集图片数：{total_images}\n"
            f"当前第1页/共1页",
        )
    if query:
        await query.answer()


async def main():
    init_db()
    dp = Dispatcher()
    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

