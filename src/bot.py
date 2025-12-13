from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, LinkPreviewOptions, Message, User as TelegramUser
from aiogram.exceptions import TelegramConflictError

from .config import settings
from .db import PaymentOrder, Resource, SearchButton, SharkPaymentConfig, User, VipPlan, db_session, init_db
from .services.payment_service import SharkPaymentService
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
    
    if not keyword or not keyword.strip():
        print(f"[Bot] ⚠️ 消息没有文本内容或关键词为空，跳过处理")
        print(f"[Bot]   消息类型: {message.content_type if hasattr(message, 'content_type') else 'unknown'}")
        print(f"[Bot]   消息 ID: {message.message_id}")
        return
    
    # 确保关键词已去除首尾空格
    keyword = keyword.strip()
    
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
        
        keyword = payload.get("k", "").strip()
        category = payload.get("f", "all")
        page = max(payload.get("p", 1), 1)
        
        # 调试日志
        print(f"[Bot] 🔍 回调数据: action={action}, keyword={repr(keyword)}, category={category}, page={page}, payload={payload}")
        
        # 如果是筛选操作且关键词为空，尝试从消息文本中恢复关键词
        if action == "filter" and not keyword:
            # 尝试从搜索结果消息文本中解析关键词
            # 消息格式: "👤 来自：...\n🔍 关键词：「...」\n\n..."
            original_message = query.message
            if original_message and original_message.text:
                import re
                # 匹配 "🔍 关键词：「...」" 格式
                match = re.search(r'🔍\s*关键词：?「([^」]*)」', original_message.text)
                if match:
                    keyword = match.group(1).strip()
                    print(f"[Bot] 🔄 从消息文本中恢复关键词: {repr(keyword)}")
                else:
                    # 如果消息是回复消息，尝试从被回复的消息中获取关键词
                    if original_message.reply_to_message:
                        replied_msg = original_message.reply_to_message
                        if replied_msg.text:
                            keyword = replied_msg.text.strip()
                            print(f"[Bot] 🔄 从被回复的消息中恢复关键词: {repr(keyword)}")
                        elif replied_msg.caption:
                            keyword = replied_msg.caption.strip()
                            print(f"[Bot] 🔄 从被回复的消息说明中恢复关键词: {repr(keyword)}")
            
            # 如果仍然没有关键词，允许筛选操作（因为用户已经看到了搜索结果，说明关键词是存在的）
            # 这种情况下，我们允许筛选，但会在搜索时使用空关键词（这实际上会显示所有资源）
            if not keyword:
                print(f"[Bot] ⚠️ 筛选操作：关键词在 callback_data 中丢失且无法恢复，但允许继续（用户已看到搜索结果）")
                # 不拒绝操作，允许继续，但记录警告
        
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

    if action in ("comic_nav", "cn"):  # "cn" 是 "comic_nav" 的缩写
        resource_id = payload.get("r") or payload.get("rid")  # 兼容旧版本
        page = max(payload.get("p", 1), 1)
        if not resource_id:
            await query.answer("资源ID丢失，请重新打开漫画", show_alert=True)
            return
        await send_comic_page(
            chat_id=query.message.chat.id,
            user=query.from_user,
            resource_id=resource_id,
            page=page,
            query=query,
        )
        return

    if action == "buy_vip":
        plan_id = payload.get("plan_id")
        if not plan_id:
            await query.answer("套餐ID丢失", show_alert=True)
            return
        
        # 检查用户ID是否匹配
        expected_user_id = payload.get("u")
        if expected_user_id is None or (query.from_user and query.from_user.id != expected_user_id):
            await query.answer("只有发送请求的用户才能操作", show_alert=True)
            return
        
        await handle_buy_vip(
            chat_id=query.message.chat.id,
            user=query.from_user,
            plan_id=plan_id,
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
            reference_time=datetime.now(timezone.utc),
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

        # 禁用链接预览
        link_preview_options = LinkPreviewOptions(is_disabled=True)

        if query:
            await query.message.edit_text(
                html,
                parse_mode="HTML",
                reply_markup=keyboard,
                link_preview_options=link_preview_options,
            )
            await query.answer()
        else:
            print(f"[Bot] 准备回复消息到聊天: {message.chat.id if message else 'None'}")
            print(f"[Bot] 聊天类型: {message.chat.type if message else 'None'}")
            try:
                # 在频道中，尝试使用 reply 或 send_message
                if message.chat.type in ("channel", "supergroup"):
                    print(f"[Bot] 检测到频道/超级群组，使用 reply 方法")
                    await message.reply(
                        html,
                        parse_mode="HTML",
                        reply_markup=keyboard,
                        link_preview_options=link_preview_options,
                    )
                else:
                    await message.reply(
                        html,
                        parse_mode="HTML",
                        reply_markup=keyboard,
                        link_preview_options=link_preview_options,
                    )
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
                        link_preview_options=link_preview_options,
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
                # 获取 VIP 套餐和支付配置
                plans = (
                    session.query(VipPlan)
                    .filter(VipPlan.is_active == True)
                    .order_by(VipPlan.sort_order.asc(), VipPlan.id.asc())
                    .all()
                )
                payment_config = (
                    session.query(SharkPaymentConfig)
                    .filter(SharkPaymentConfig.is_active == True)
                    .first()
                )
                
                # 构建 VIP 提示消息
                message_text = "🔒 此内容仅限 VIP 会员访问\n\n"
                
                if plans:
                    message_text += "💰 <b>VIP 套餐：</b>\n"
                    buttons = []
                    for plan in plans:
                        message_text += f"• {plan.name}：¥{plan.price}（{plan.duration_days}天）\n"
                        # 为每个套餐创建支付按钮
                        if payment_config:
                            buttons.append([
                                InlineKeyboardButton(
                                    text=f"💳 购买 {plan.name}",
                                    callback_data=json.dumps({
                                        "a": "buy_vip",
                                        "plan_id": plan.id,
                                        "u": user.id if user else 0,
                                    })
                                )
                            ])
                    message_text += "\n"
                
                if not payment_config:
                    # 如果没有配置支付信息，使用旧的充值链接
                    recharge_url = settings.vip_recharge_url
                    message_text += f"点击下方链接开通 VIP：\n{recharge_url}"
                else:
                    message_text += "💳 点击下方按钮选择套餐并完成支付\n"
                
                keyboard = InlineKeyboardMarkup(inline_keyboard=buttons) if buttons else None
                
                await bot.send_message(
                    chat_id,
                    message_text,
                    parse_mode="HTML",
                    reply_markup=keyboard,
                )
                if query:
                    await query.answer("请先开通 VIP", show_alert=True)
                return

        # 分页发送图片，每页显示 page_size 张图片
        # 如果总图片数 <= 10，只显示 1 页，不分页
        page_size = settings.bot.page_size
        if total_images <= 10:
            # 少于等于 10 张图片，只显示 1 页，不分页
            total_pages = 1
            page = 1
            page_files = repo.list_comic_files(resource_id, limit=total_images, offset=0)
        else:
            # 超过 10 张图片，使用分页
            total_pages = (total_images + page_size - 1) // page_size  # 向上取整
            # 确保 page 在有效范围内
            page = max(1, min(page, total_pages))
            # 计算当前页的偏移量
            offset = (page - 1) * page_size
            page_files = repo.list_comic_files(resource_id, limit=page_size, offset=offset)
        
        if not page_files:
            await bot.send_message(chat_id, "该页没有内容。")
            if query:
                await query.answer()
            return
        
        # 发送当前页的图片（每10张一组）
        for chunk in chunk_list(page_files, 10):
            media_group = [InputMediaPhoto(media=item.file_id) for item in chunk]
            await bot.send_media_group(chat_id, media_group)
        
        # 发送分页导航按钮（如果只有 1 页，不显示分页按钮）
        link_preview_options = LinkPreviewOptions(is_disabled=True)
        if total_pages > 1:
            keyboard = build_comic_nav_keyboard(resource_id, page, total_pages)
            await bot.send_message(
                chat_id,
                f"📖 <b>{resource.title}</b>\n"
                f"📊 合集图片数：{total_images}\n"
                f"📄 当前第 {page} 页 / 共 {total_pages} 页",
                reply_markup=keyboard,
                parse_mode="HTML",
                link_preview_options=link_preview_options,
            )
        else:
            # 只有 1 页，不显示分页按钮
            await bot.send_message(
                chat_id,
                f"📖 <b>{resource.title}</b>\n"
                f"📊 合集图片数：{total_images}",
                parse_mode="HTML",
                link_preview_options=link_preview_options,
            )
    if query:
        await query.answer()


async def handle_buy_vip(
    *,
    chat_id: int,
    user,
    plan_id: int,
    query: CallbackQuery | None = None,
):
    """处理购买VIP请求"""
    import time
    import httpx
    
    print(f"[Bot] ========== handle_buy_vip 开始 ==========")
    print(f"[Bot] plan_id={plan_id}, user_id={user.id if user else 'None'}")
    
    with db_session() as session:
        # 获取VIP套餐
        vip_plan = session.get(VipPlan, plan_id)
        if not vip_plan or not vip_plan.is_active:
            await bot.send_message(chat_id, "套餐不存在或已停用。")
            if query:
                await query.answer("套餐不存在", show_alert=True)
            return
        
        # 获取支付配置
        payment_config = (
            session.query(SharkPaymentConfig)
            .filter(SharkPaymentConfig.is_active == True)
            .first()
        )
        if not payment_config:
            await bot.send_message(chat_id, "支付系统未配置，请联系管理员。")
            if query:
                await query.answer("支付系统未配置", show_alert=True)
            return
        
        # 生成订单号
        order_id = f"VIP{user.id}{int(time.time())}"
        
        # 创建订单记录
        order = PaymentOrder(
            order_id=order_id,
            user_id=user.id,
            vip_plan_id=plan_id,
            amount=vip_plan.price,
            status="unpaid",
            channel_type=payment_config.channel_type,
        )
        session.add(order)
        session.flush()
        
        # 调用支付接口创建订单
        payment_service = SharkPaymentService(
            merchant_id=payment_config.merchant_id,
            sign_key=payment_config.sign_key,
            api_base_url=payment_config.api_base_url,
        )
        
        try:
            # 检查通道类型是否配置
            if not payment_config.channel_type or not payment_config.channel_type.strip():
                error_msg = "支付配置中未设置通道类型，请联系管理员配置"
                await bot.send_message(chat_id, f"创建订单失败：{error_msg}")
                if query:
                    await query.answer("创建订单失败", show_alert=True)
                return
            
            result = await payment_service.create_order(
                order_id=order_id,
                order_amount=vip_plan.price,
                notify_url=payment_config.notify_url,
                channel_type=payment_config.channel_type,
                return_url=payment_config.return_url,
                payer_id=str(user.id),
                order_title=f"VIP套餐-{vip_plan.name}",
                order_body=f"购买{vip_plan.name}，有效期{vip_plan.duration_days}天",
            )
            
            if result.get("code") != 200:
                error_msg = result.get("msg", "创建订单失败")
                await bot.send_message(chat_id, f"创建订单失败：{error_msg}")
                if query:
                    await query.answer("创建订单失败", show_alert=True)
                return
            
            pay_url = result.get("data", {}).get("payUrl", "")
            if not pay_url:
                await bot.send_message(chat_id, "未获取到支付链接，请稍后重试。")
                if query:
                    await query.answer("获取支付链接失败", show_alert=True)
                return
            
            # 更新订单支付链接
            order.pay_url = pay_url
            session.flush()
            
            # 发送支付链接
            message_text = (
                f"💰 <b>订单创建成功</b>\n\n"
                f"📦 套餐：{vip_plan.name}\n"
                f"💵 金额：¥{vip_plan.price}\n"
                f"⏰ 有效期：{vip_plan.duration_days}天\n"
                f"📋 订单号：{order_id}\n\n"
                f"点击下方链接完成支付："
            )
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="💳 立即支付", url=pay_url)
            ]])
            
            await bot.send_message(
                chat_id,
                message_text,
                parse_mode="HTML",
                reply_markup=keyboard,
            )
            
            if query:
                await query.answer("订单已创建，请完成支付", show_alert=False)
            
            print(f"[Bot] ✅ 订单创建成功: order_id={order_id}, pay_url={pay_url}")
            
        except Exception as e:
            print(f"[Bot] ❌ 创建支付订单失败: {e}")
            import traceback
            traceback.print_exc()
            await bot.send_message(chat_id, f"创建订单失败：{str(e)}")
            if query:
                await query.answer("创建订单失败", show_alert=True)


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
        
        # 等待一段时间，确保之前的实例完全关闭
        print(f"[Bot] 等待 3 秒以确保之前的实例完全关闭...")
        await asyncio.sleep(3)
        
        # 检查是否有其他实例在运行
        try:
            me = await bot.get_me()
            print(f"[Bot] 机器人信息: @{me.username} (ID: {me.id})")
        except Exception as e:
            print(f"[Bot] ❌ 无法获取机器人信息: {e}")
            print(f"[Bot] ⚠️  可能的原因：")
            print(f"[Bot]    1. BOT_TOKEN 无效或已过期")
            print(f"[Bot]    2. 机器人已被删除或禁用")
            print(f"[Bot]    3. Token 格式不正确")
            print(f"[Bot] 💡 解决方案：")
            print(f"[Bot]    1. 前往 @BotFather 检查机器人状态")
            print(f"[Bot]    2. 如果机器人不存在，创建新机器人并获取新 token")
            print(f"[Bot]    3. 如果机器人存在，使用 /revoke 撤销旧 token，然后 /token 获取新 token")
            print(f"[Bot]    4. 将新 token 更新到 .env 文件中的 BOT_TOKEN")
            raise
        
        dp = Dispatcher()
        dp.include_router(router)
        print(f"[Bot] 机器人启动中...")
        print(f"[Bot] 搜索频道 ID: {settings.channels.search_channel_id}")
        print(f"[Bot] 机器人 Token: {settings.bot_token[:10]}...")
        print(f"[Bot] 开始轮询更新...")
        print(f"[Bot] ==================================")
        
        try:
            await dp.start_polling(bot, drop_pending_updates=True)
        except TelegramConflictError as e:
            print(f"[Bot] ❌ Telegram 冲突错误: {e}")
            print(f"[Bot] ⚠️  检测到多个 bot 实例正在运行！")
            print(f"[Bot] 💡 解决方案：")
            print(f"[Bot]    1. 运行 ./stop.sh 停止所有服务")
            print(f"[Bot]    2. 检查是否有其他进程在使用同一个 BOT_TOKEN:")
            print(f"[Bot]       ps aux | grep 'python.*bot'")
            print(f"[Bot]       ps aux | grep 'src.bot'")
            print(f"[Bot]    3. 如果有其他进程，使用 kill <PID> 终止它们")
            print(f"[Bot]    4. 等待 10-30 秒后重新启动")
            print(f"[Bot]    5. 如果问题持续，检查是否有 webhook 设置:")
            print(f"[Bot]       运行: python clear_webhook.py")
            raise
    except TelegramConflictError:
        # 已经在上面的 except 块中处理了，直接重新抛出
        raise
    except Exception as e:
        print(f"[Bot] 启动失败: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    asyncio.run(main())

