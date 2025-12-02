#!/bin/bash

# 停止脚本 - Telegram Bot 搜索系统
# 使用方法: ./stop.sh

echo "🛑 停止 Telegram Bot 搜索系统..."

# 停止后端服务
if [ -f ".backend.pid" ]; then
    BACKEND_PID=$(cat .backend.pid)
    if ps -p $BACKEND_PID > /dev/null 2>&1; then
        echo "   停止后端服务 (PID: $BACKEND_PID)..."
        kill $BACKEND_PID
        rm .backend.pid
    fi
fi

# 停止机器人服务
if [ -f ".bot.pid" ]; then
    BOT_PID=$(cat .bot.pid)
    if ps -p $BOT_PID > /dev/null 2>&1; then
        echo "   停止机器人服务 (PID: $BOT_PID)..."
        kill $BOT_PID
        rm .bot.pid
    fi
fi

# 停止前端服务
if [ -f ".frontend.pid" ]; then
    FRONTEND_PID=$(cat .frontend.pid)
    if ps -p $FRONTEND_PID > /dev/null 2>&1; then
        echo "   停止前端服务 (PID: $FRONTEND_PID)..."
        kill $FRONTEND_PID
        rm .frontend.pid
    fi
fi

# 清理可能残留的进程
echo "   清理可能残留的进程..."
pkill -f "uvicorn src.web:app" 2>/dev/null || true
pkill -f "python.*src.bot" 2>/dev/null || true
pkill -f "python -m src.bot" 2>/dev/null || true
pkill -f "python3.*src.bot" 2>/dev/null || true
pkill -f "next dev" 2>/dev/null || true

# 等待进程完全终止
sleep 2

# 清理 Next.js 锁文件
if [ -d ".next/dev" ]; then
    rm -rf .next/dev/lock 2>/dev/null || true
    echo "   清理 Next.js 锁文件..."
fi

echo "✅ 所有服务已停止"

