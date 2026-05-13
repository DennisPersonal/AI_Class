#!/bin/bash
# =============================================================
# AI小课堂 - 系统关闭脚本
# =============================================================

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
PORT=5000

echo "=========================================="
echo "  🛑 AI小课堂 - 系统关闭"
echo "=========================================="
echo ""

# 查找并关闭占用端口的进程
PID=$(lsof -ti :$PORT 2>/dev/null)

if [ -z "$PID" ]; then
    echo "ℹ️  未检测到运行中的服务器 (端口 $PORT)"
else
    echo "🔍 找到服务器进程 PID: $PID"
    kill $PID 2>/dev/null
    sleep 1

    # 确认关闭
    if kill -0 $PID 2>/dev/null; then
        echo "⏳ 进程未响应，强制关闭..."
        kill -9 $PID 2>/dev/null
        sleep 1
    fi

    if lsof -ti :$PORT &>/dev/null; then
        echo "❌ 关闭失败，请手动执行: kill -9 $PID"
        exit 1
    else
        echo "✅ 服务器已关闭"
    fi
fi

# 清理日志
echo ""
read -p "🧹 是否删除运行日志? (y/N): " clean_log
if [[ "$clean_log" == "y" || "$clean_log" == "Y" ]]; then
    rm -f "$PROJECT_DIR/server.log" 2>/dev/null
    echo "✅ 日志已清理"
fi

echo ""
echo "=========================================="
echo "  系统已安全关闭"
echo "=========================================="
