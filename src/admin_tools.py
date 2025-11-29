from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from .config import settings
from .db import db_session, Resource

admin_router = Router()


@admin_router.message(Command("add_resource"))
async def handle_add_resource(message: Message):
    if message.from_user.id not in map(int, (settings.bot.search_channel_id,)):
        await message.answer("无权限")
        return
    await message.answer("请直接转发资源到预览频道，随后使用 /bind_preview 命令绑定。")

