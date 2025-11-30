#!/bin/bash

# 启动脚本 - Telegram Bot 搜索系统
# 使用方法: ./start.sh

set -e

echo "🚀 启动 Telegram Bot 搜索系统..."

# 检查 Python 虚拟环境
if [ ! -d ".venv" ]; then
    echo "📦 创建 Python 虚拟环境..."
    python3 -m venv .venv
fi

# 激活虚拟环境
echo "🔧 激活 Python 虚拟环境..."
source .venv/bin/activate

# 安装 Python 依赖
echo "📥 安装 Python 依赖..."
pip install -q -r requirements.txt

# 检查 Node.js 依赖
if [ ! -d "node_modules" ]; then
    echo "📦 安装 Node.js 依赖..."
    pnpm install
fi

# 检查 .env 文件
if [ ! -f ".env" ]; then
    echo "⚠️  警告: 未找到 .env 文件，请确保已配置环境变量"
fi

# 启动后端服务（后台运行）
echo "🔧 启动后端服务 (FastAPI)..."
# 增加超时时间和文件大小限制以支持大文件上传
uvicorn src.web:app --host 0.0.0.0 --port 8000 --reload --timeout-keep-alive 300 --limit-concurrency 1000 > backend.log 2>&1 &
BACKEND_PID=$!
echo "   后端服务 PID: $BACKEND_PID"

# 等待后端启动
sleep 3

# 启动机器人服务（后台运行）
echo "🤖 启动机器人服务..."
python -m src.bot > bot.log 2>&1 &
BOT_PID=$!
echo "   机器人服务 PID: $BOT_PID"

# 等待机器人启动
sleep 2

# 启动前端服务（后台运行）
echo "🌐 启动前端服务 (Next.js)..."
cd "$(dirname "$0")"
pnpm dev > frontend.log 2>&1 &
FRONTEND_PID=$!
echo "   前端服务 PID: $FRONTEND_PID"

# 保存 PID 到文件
echo $BACKEND_PID > .backend.pid
echo $BOT_PID > .bot.pid
echo $FRONTEND_PID > .frontend.pid

echo ""
echo "✅ 所有服务已启动！"
echo ""
echo "📊 服务状态:"
echo "   - 后端 API:    http://127.0.0.1:8000"
echo "   - 前端管理面板: http://localhost:3000"
echo "   - 机器人:      运行中"
echo ""
echo "📝 日志文件:"
echo "   - 后端日志:    backend.log"
echo "   - 机器人日志:  bot.log"
echo "   - 前端日志:    frontend.log"
echo ""
echo "🛑 停止服务: ./stop.sh"
echo ""

