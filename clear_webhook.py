#!/usr/bin/env python3
"""清除 Telegram Bot 的 webhook 设置"""

import asyncio
from aiogram import Bot
from dotenv import load_dotenv
import os

load_dotenv()

async def clear_webhook():
    bot_token = os.environ.get("BOT_TOKEN")
    if not bot_token:
        print("❌ 未找到 BOT_TOKEN 环境变量")
        return
    
    bot = Bot(token=bot_token)
    try:
        # 删除 webhook
        result = await bot.delete_webhook(drop_pending_updates=True)
        print(f"✅ Webhook 已清除: {result}")
        
        # 检查当前 webhook 状态
        webhook_info = await bot.get_webhook_info()
        print(f"📋 Webhook 信息: {webhook_info.url or '未设置'}")
        
    except Exception as e:
        print(f"❌ 清除 webhook 失败: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(clear_webhook())

