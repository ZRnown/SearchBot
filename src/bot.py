from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InputMediaPhoto, Message, User as TelegramUser

from .config import settings
from .db import Resource, SearchButton, User, db_session, init_db
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
            print(f"[Bot] 收到深度链接请求: resource_id={resource_id}, 完整payload={payload[1]}")
            await send_comic_page(
                chat_id=message.chat.id,
                user=message.from_user,
                resource_id=resource_id,
                page=1,
            )
            return
    await message.answer("请输入关键字到搜索频道，即可获取资源列表。")


# 搜索处理器 - 必须放在最前面，确保优先处理搜索频道的消息
@router.message(F.chat.id == settings.channels.search_channel_id)
async def handle_search(message: Message):
    # 获取消息文本（可能是直接文本、转发消息的文本、或回复消息的文本）
    print(f"[Bot] 🔍 handle_search 被调用!")
    print(f"[Bot]   消息 ID: {message.message_id}")
    print(f"[Bot]   聊天 ID: {message.chat.id}")
    print(f"[Bot]   配置的搜索频道 ID: {settings.channels.search_channel_id}")
    print(f"[Bot]   ID 匹配检查: {message.chat.id} == {settings.channels.search_channel_id} = {message.chat.id == settings.channels.search_channel_id}")
    
    keyword = None
    if message.text:
        keyword = message.text.strip()
    elif message.caption:  # 图片/视频等带说明的消息
        keyword = message.caption.strip()
    elif message.forward_from_chat and message.forward_from_message_id:
        # 转发消息，尝试获取原始消息文本
        print(f"[Bot] ⚠️ 收到转发消息，无法直接获取文本内容")
        return
    
    if not keyword:
        print(f"[Bot] ⚠️ 消息没有文本内容，跳过处理")
        print(f"[Bot]   消息类型: {message.content_type if hasattr(message, 'content_type') else 'unknown'}")
        print(f"[Bot]   消息 ID: {message.message_id}")
        return
    
    print(f"[Bot] ========== 收到搜索请求 ==========")
    print(f"[Bot] 频道 ID: {message.chat.id}")
    print(f"[Bot] 配置的搜索频道 ID: {settings.channels.search_channel_id}")
    print(f"[Bot] ID 匹配: {message.chat.id == settings.channels.search_channel_id}")
    print(f"[Bot] 关键词: {keyword}")
    print(f"[Bot] 用户 ID: {message.from_user.id if message.from_user else 'None'}")
    print(f"[Bot] 消息 ID: {message.message_id}")
    print(f"[Bot] 聊天类型: {message.chat.type}")
    print(f"[Bot] 消息内容类型: {message.content_type if hasattr(message, 'content_type') else 'unknown'}")
    
    try:
        await respond_with_results(
            message=message,
            keyword=keyword,
            category="all",
            page=1,
        )
        print(f"[Bot] ✅ 搜索请求处理完成: {keyword}")
    except Exception as e:
        print(f"[Bot] ❌ 搜索处理错误: {e}")
        import traceback
        traceback.print_exc()
        try:
            await message.reply(f"搜索时发生错误: {str(e)}")
        except Exception as reply_error:
            print(f"[Bot] ❌ 回复消息失败: {reply_error}")
            import traceback
            traceback.print_exc()


# 通用消息跟踪处理器（放在搜索处理器之后，避免拦截搜索消息）
@router.message(flags={"block": False})
async def track_messages(message: Message):
    if not message.from_user:
        return
    with db_session() as session:
        ensure_user_record(session, message.from_user)


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
        # 检查用户ID是否匹配
        expected_user_id = payload.get("u")
        if expected_user_id is None:
            # 兼容旧版本：如果没有用户ID，允许操作（向后兼容）
            print(f"[Bot] ⚠️ 回调数据中没有用户ID，允许操作（向后兼容）")
        elif query.from_user and query.from_user.id != expected_user_id:
            # 用户ID不匹配，拒绝操作
            print(f"[Bot] ❌ 用户ID不匹配: 期望 {expected_user_id}, 实际 {query.from_user.id if query.from_user else 'None'}")
            await query.answer("只有发送搜索请求的用户才能操作此结果", show_alert=True)
            return
        
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
    print(f"[Bot] respond_with_results: keyword={keyword}, category={category}, page={page}")
    try:
        with db_session() as session:
            actor = query.from_user if query else (message.from_user if message else None)
            ensure_user_record(session, actor)
            service = SearchService(session)
            result = service.run(keyword=keyword, category=category, page=page)
            print(f"[Bot] 搜索结果: 找到 {len(result.rows)} 条记录, 总计 {result.total_pages} 页")
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
        # 获取发起搜索的用户ID
        search_user_id = (query.from_user.id if query else (message.from_user.id if message and message.from_user else None))
        if search_user_id is None:
            print(f"[Bot] ⚠️ 无法获取用户ID，使用 0 作为默认值")
            search_user_id = 0
        
        keyboard = build_keyboard(
            keyword=keyword,
            active_filter=category,
            page=page,
            total_pages=result.total_pages,
            user_id=search_user_id,
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
            print(f"[Bot] 准备回复消息到聊天: {message.chat.id if message else 'None'}")
            print(f"[Bot] 聊天类型: {message.chat.type if message else 'None'}")
            try:
                # 在频道中，尝试使用 reply 或 send_message
                if message.chat.type in ("channel", "supergroup"):
                    print(f"[Bot] 检测到频道/超级群组，使用 reply 方法")
                    await message.reply(html, parse_mode="HTML", reply_markup=keyboard)
                else:
                    await message.reply(html, parse_mode="HTML", reply_markup=keyboard)
                print(f"[Bot] ✅ 消息已成功发送")
            except Exception as send_error:
                print(f"[Bot] ❌ 发送消息失败: {send_error}")
                import traceback
                traceback.print_exc()
                # 如果 reply 失败，尝试使用 send_message
                try:
                    print(f"[Bot] 尝试使用 send_message 方法")
                    await bot.send_message(
                        message.chat.id,
                        html,
                        parse_mode="HTML",
                        reply_markup=keyboard,
                        reply_to_message_id=message.message_id,
                    )
                    print(f"[Bot] ✅ 使用 send_message 成功发送")
                except Exception as send_msg_error:
                    print(f"[Bot] ❌ send_message 也失败: {send_msg_error}")
                    raise
    except Exception as e:
        print(f"[Bot] respond_with_results 错误: {e}")
        import traceback
        traceback.print_exc()
        raise


async def send_comic_page(
    *,
    chat_id: int,
    user,
    resource_id: str,
    page: int,
    query: CallbackQuery | None = None,
):
    print(f"[Bot] ========== send_comic_page 开始 ==========")
    print(f"[Bot] resource_id={resource_id} (类型: {type(resource_id)})")
    print(f"[Bot] user_id={user.id if user else 'None'}")
    print(f"[Bot] chat_id={chat_id}")
    
    with db_session() as session:
        repo = ResourceRepository(session)
        
        # 尝试直接查询数据库
        print(f"[Bot] 尝试查询资源: resource_id={resource_id}")
        resource = repo.get(resource_id)
        
        # 如果查询失败，尝试查找所有资源看看是否有匹配的
        if not resource:
            print(f"[Bot] ⚠️ 直接查询失败，尝试查找所有资源...")
            all_resources = session.query(Resource).limit(10).all()
            print(f"[Bot] 数据库中的资源示例: {[(r.id, r.title, r.type) for r in all_resources]}")
            
            # 尝试使用字符串匹配查找
            try:
                resource_by_query = session.query(Resource).filter(Resource.id == resource_id).first()
                print(f"[Bot] 使用 filter 查询结果: {resource_by_query}")
                resource = resource_by_query
            except Exception as e:
                print(f"[Bot] ❌ filter 查询出错: {e}")
        
        print(f"[Bot] 最终查询结果:")
        print(f"[Bot]   - resource: {resource}")
        print(f"[Bot]   - resource.id: {resource.id if resource else 'None'}")
        print(f"[Bot]   - resource.type: {resource.type if resource else 'None'}")
        print(f"[Bot]   - resource.title: {resource.title if resource else 'None'}")
        
        if not resource:
            print(f"[Bot] ❌ 资源不存在: resource_id={resource_id}")
            if query:
                await query.answer("漫画不存在", show_alert=True)
            else:
                await bot.send_message(chat_id, "漫画不存在或已下架。")
            return
        if resource.type != "comic":
            print(f"[Bot] ❌ 资源类型不匹配: resource_id={resource_id}, type={resource.type}, 期望=comic")
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

        # 检查资源是否需要VIP权限
        if resource.is_vip:
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
    try:
        init_db()
        
        # 清除 webhook 并丢弃待处理的更新
        print(f"[Bot] ========== 机器人启动 ==========")
        print(f"[Bot] 清除 webhook...")
        try:
            webhook_info = await bot.get_webhook_info()
            print(f"[Bot] 当前 webhook 信息: {webhook_info.url if webhook_info.url else '未设置'}")
            await bot.delete_webhook(drop_pending_updates=True)
            print(f"[Bot] ✅ Webhook 已清除")
        except Exception as e:
            print(f"[Bot] ⚠️  清除 webhook 时出错（可能没有 webhook）: {e}")
        
        # 检查是否有其他实例在运行
        try:
            me = await bot.get_me()
            print(f"[Bot] 机器人信息: @{me.username} (ID: {me.id})")
        except Exception as e:
            print(f"[Bot] ❌ 无法获取机器人信息: {e}")
            raise
        
        dp = Dispatcher()
        dp.include_router(router)
        print(f"[Bot] 机器人启动中...")
        print(f"[Bot] 搜索频道 ID: {settings.channels.search_channel_id}")
        print(f"[Bot] 机器人 Token: {settings.bot_token[:10]}...")
        print(f"[Bot] 开始轮询更新...")
        print(f"[Bot] ==================================")
        await dp.start_polling(bot, drop_pending_updates=True)
    except Exception as e:
        print(f"[Bot] 启动失败: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    asyncio.run(main())

