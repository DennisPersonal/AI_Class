#!/bin/bash
# =============================================================
# AI小课堂 - 一键启动脚本
# 用法: ./start.sh
# =============================================================

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
PORT=5000
LOG_FILE="$PROJECT_DIR/server.log"

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║     🎓  AI小课堂 · 系统启动                  ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# ==================== 1. 检查 Python ====================
echo "🔍 1/5 检测 Python 环境..."
if ! command -v python3 &> /dev/null; then
    echo "   ❌ 未找到 python3，请先安装 Python 3.8+"
    exit 1
fi
PY_VER=$(python3 --version 2>&1)
echo "   ✅ $PY_VER"

# ==================== 2. 检查依赖 ====================
echo ""
echo "📦 2/5 检测 Python 依赖..."
DEPS=("flask" "requests")
# edge_tts 可选，不阻塞启动
OPT_DEPS=("edge_tts")
MISSING=0

check_dep() {
    local dep=$1
    local optional=$2
    if python3 -c "import $dep" 2>/dev/null; then
        echo "   ✅ $dep 已安装"
        return 0
    else
        if [ "$optional" = "true" ]; then
            echo "   ⏳ $dep 未安装，尝试自动安装..."
        else
            echo "   ⏳ $dep 未安装，正在自动安装..."
        fi
        pip3 install "$dep" -q 2>/dev/null
        if python3 -c "import $dep" 2>/dev/null; then
            echo "   ✅ $dep 安装成功"
            return 0
        else
            if [ "$optional" = "true" ]; then
                echo "   ⚠️  $dep 安装失败（可选依赖，不影响启动）"
                return 0
            else
                echo "   ❌ $dep 安装失败"
                MISSING=1
                return 1
            fi
        fi
    fi
}

for dep in "${DEPS[@]}"; do check_dep "$dep" "false"; done
for dep in "${OPT_DEPS[@]}"; do check_dep "$dep" "true"; done

# 检测 macOS say 命令（TTS fallback 用）
if command -v say &> /dev/null; then
    echo "   ✅ macOS TTS (say) 已就绪"
else
    echo "   ⚠️  macOS TTS (say) 不可用，语音将使用浏览器 TTS"
fi

# 检测 lsof（端口检测用）
if ! command -v lsof &> /dev/null; then
    echo "   ⚠️  未找到 lsof，将跳过端口检测"
    SKIP_PORT_CHECK=true
fi

if [ "$MISSING" -eq 1 ]; then
    echo ""
    echo "❌ 必要依赖安装不完整，请手动安装后重试"
    exit 1
fi

# ==================== 3. 检查端口 ====================
echo ""
echo "🔌 3/5 检测端口 ${PORT} 占用..."
if [ "$SKIP_PORT_CHECK" != "true" ] && lsof -i :$PORT &>/dev/null 2>&1; then
    OLD_PID=$(lsof -ti :$PORT)
    echo "   ⚠️  端口 $PORT 已被 PID $OLD_PID 占用，正在关闭..."
    kill $OLD_PID 2>/dev/null
    sleep 1
    if lsof -i :$PORT &>/dev/null 2>&1; then
        kill -9 $OLD_PID 2>/dev/null
        sleep 1
    fi
    echo "   ✅ 端口已释放"
else
    echo "   ✅ 端口 $PORT 可用"
fi

# ==================== 4. 清理旧缓存 ====================
echo ""
echo "🧹 4/5 清理旧音频缓存..."
python3 -c "
import os
cache_dir = '$PROJECT_DIR/audio_cache'
if os.path.isdir(cache_dir):
    total = 0
    for f in os.listdir(cache_dir):
        fp = os.path.join(cache_dir, f)
        if os.path.isfile(fp):
            size = os.path.getsize(fp)
            total += size
    print(f'   ✅ 缓存目录: {len(os.listdir(cache_dir))} 个文件 ({total/1024:.0f} KB)')
else:
    print('   ✅ 无需清理')
"

# ==================== 5. 启动服务 ====================
echo ""
echo "🚀 5/5 启动服务器..."
cd "$PROJECT_DIR"
nohup python3 app.py > "$LOG_FILE" 2>&1 &
SERVER_PID=$!

# 等待服务就绪
echo -n "   等待服务就绪"
for i in $(seq 1 10); do
    if curl -s "http://localhost:$PORT" > /dev/null 2>&1; then
        echo ""
        echo "   ✅ 服务已就绪 (PID: $SERVER_PID)"
        break
    fi
    echo -n "."
    sleep 0.5
done

if ! kill -0 $SERVER_PID 2>/dev/null; then
    echo ""
    echo "❌ 服务器启动失败，请查看日志:"
    tail -30 "$LOG_FILE"
    exit 1
fi

# ==================== 完成 ====================
LOCAL_IP="localhost"
if command -v ipconfig &> /dev/null; then
    LOCAL_IP=$(ipconfig getifaddr en0 2>/dev/null || echo "$LOCAL_IP")
fi

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║   ✅  AI小课堂 启动完成！                     ║"
echo "╠══════════════════════════════════════════════╣"
echo "║   📍 本地访问:  http://localhost:$PORT          ║"
echo "║   📍 局域网:    http://$LOCAL_IP:$PORT        ║"
echo "║   📄 日志:      $LOG_FILE  ║"
echo "║   🛑 关闭:      ./shutdown.sh                ║"
echo "╠══════════════════════════════════════════════╣"
echo "║   🎤 语音指令: \"开始抽取同学\"                 ║"
echo "║   🎯 设定人数: \"设定一次抽取N个\"              ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# 自动打开浏览器
if [[ "$OSTYPE" == "darwin"* ]]; then
    open "http://localhost:$PORT" 2>/dev/null
fi
