import os, subprocess, uuid, hashlib, time
from flask import Flask, request, jsonify, render_template, send_from_directory
import requests
import random
import re

app = Flask(__name__)

# 音频缓存目录
AUDIO_DIR = os.path.join(os.path.dirname(__file__), 'audio_cache')
os.makedirs(AUDIO_DIR, exist_ok=True)

# macOS TTS 语音名称（中文 - 婷婷，自然清晰）
TTS_VOICE = 'Tingting'
TTS_RATE = 175  # 语速（默认175，可调）

# ====================== 填入你的 DeepSeek API Key ======================
DEEPSEEK_API_KEY = "sk-f6d458991739464780208bd1eac58056"
# ======================================================================

# 会话记忆（用于AI多轮对话）
conversation_history = []

# 42名学生数据
STUDENT_NAMES = ["鲍沐依","蔡晋轩","蔡慕凡","陈一诺","陈子元","程尹芯","丁曦苒","段毓瑶","樊知益","冯俊钦","冯翊朗","付奕谦","高诺希","顾晋晗","顾子瑶","胡靖伟","贾钧贺","李佳琪","李馨妍","李艺苒","李逸灿","刘佳霖","刘雨晴","刘悦彤","刘宗炎","毛默犁","孟凡圣","宋景屹","王初昭","王鸿毅","吴栎添","徐梓洋","余佳恩","于可铭","于沐汐","俞知鹭","袁润豪","张芃杨","张清妍","赵糯米","周希羽","宗吴宜"]

import colorsys
def name_color(index, total):
    hue = index / total
    r, g, b = colorsys.hsv_to_rgb(hue, 0.8, 0.9)
    return f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"

students = []
for i, name in enumerate(STUDENT_NAMES):
    students.append({
        "id": i+1,
        "name": name,
        "color": name_color(i, len(STUDENT_NAMES))
    })

# 已抽取人员ID列表
awarded = []
# 每次抽取人数（默认5人）
draw_count = 5


# ==================== 中文数字转阿拉伯数字 ====================
CN_NUM_MAP = {
    "零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
    "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10
}

def chinese_to_number(s: str):
    """将纯中文数字（一到十亿）转为 int，失败返回 None"""
    s = s.strip()
    # 直接查表（处理 0-10）
    if s in CN_NUM_MAP:
        return CN_NUM_MAP[s]
    # 十一～十九
    m = re.match(r'^十([一二三四五六七八九])$', s)
    if m:
        return 10 + CN_NUM_MAP.get(m.group(1), 0)
    # 二十～九十九
    m = re.match(r'^([二三四五六七八九])十([一二三四五六七八九])?$', s)
    if m:
        tens = CN_NUM_MAP.get(m.group(1), 0)
        ones = CN_NUM_MAP.get(m.group(2), 0) if m.group(2) else 0
        return tens * 10 + ones
    # 一百
    if s == "一百":
        return 100
    return None


# ==================== 路由 ====================

@app.route('/')
def index():
    return render_template('index.html', students=students)


@app.route('/guide')
def guide():
    return render_template('guide.html')


# AI 对话接口
@app.route('/api/ai', methods=['POST'])
def ai_chat():
    global draw_count

    text = request.json.get('text', '').strip()
    if not text:
        return jsonify({"reply": "我听不见哦～请再讲一次～", "command": "", "action": "normal"})

    # === 1. 指令：开始抽取同学 → 触发前端抽取动作 ===
    if "开始抽取同学" in text:
        return jsonify({
            "reply": "好嘞！开始抽取啦～",
            "command": "start_lottery",
            "action": "wave"
        })

    # === 2. 指令：设定一次抽取N个（支持中文数字和阿拉伯数字） ===
    # 匹配 "设定一次抽取3个" 或 "设定一次抽取三个"
    set_match = re.search(r'设定一次抽取([\d]+)', text)
    if set_match:
        n = int(set_match.group(1))
    else:
        set_match_cn = re.search(r'设定一次抽取([零一二三四五六七八九十两百]+)', text)
        if set_match_cn:
            n = chinese_to_number(set_match_cn.group(1))
        else:
            n = None

    if n is not None and n > 0:
        draw_count = n
        reply = f"收到设定指令，下次抽取人数为{draw_count}人"
        return jsonify({
            "reply": reply,
            "command": "set_count",
            "action": "normal"
        })
    elif n is not None and n <= 0:
        draw_count = 1
        reply = "最少要抽取1位小朋友哦，已设定为1人～"
        return jsonify({
            "reply": reply,
            "command": "set_count",
            "action": "normal"
        })

    # === 3. 指令：你支持哪些指令 → 优先回答系统指令 ===
    keywords_support = ["支持","指令","你会什么","你能做什么","可以做什么","有啥功能","有什么功能","能做什么","会些什么"]
    if any(k in text for k in keywords_support):
        reply = (
            "小艾可以帮你做这些事哦：\n"
            "1️⃣ 说「开始抽取同学」—— 3D球面抽奖，随机选幸运小朋友上台互动！\n"
            "2️⃣ 说「设定一次抽取N个」—— 比如「设定一次抽取五个」，一次抽5人。\n"
            "3️⃣ 问学习问题—— 小艾可以解答四年级的语数英疑问，讲历史故事、背古诗、做趣味数学题、科普小知识，陪你聊天！"
        )
        return jsonify({"reply": reply, "command": "", "action": "normal"})

    # === 4. 指令：介绍一下你自己 → 用古诗词修辞 ===
    keywords_intro = ["介绍你自己","你是谁","自我介绍","你的名字","你叫什么","你是哪位","介绍一下你"]
    if any(k in text for k in keywords_intro):
        reply = (
            "小朋友们好呀！我是小艾，是你们AI课堂的小助手。\n\n"
            "「青青子衿，悠悠我心」—— 我就像一位藏在屏幕里的小书童，\n"
            "伴你读书、陪你吟诗、和你一起探索这个大大的世界。\n\n"
            "我会抽奖送同学上台展示，\n"
            "也会回答你们的每一个「为什么」。\n\n"
            "书山有路勤为径，学海无涯乐作舟——\n"
            "让我们在欢声笑语中，一起长大吧！✨"
        )
        return jsonify({"reply": reply, "command": "", "action": "normal"})

    # === 5. 普通语音 → 调用DeepSeek API（带会话记忆） ===
    system_prompt = (
        "你是AI课堂小助手小艾，面向四年级小学生，说话简短亲切有文采，"
        "可以引用古诗词或优美语言来回答问题，让小朋友感受到文学的韵味。"
        "回答控制在80字以内，温暖鼓励的语气，像大姐姐一样。"
        "注意：小朋友通过语音输入，可能会识别不准。"
        "如果当前句子不通顺，结合之前的对话推测真正意图，然后自然回答。"
    )

    # 构建带记忆的messages数组
    messages = [{"role": "system", "content": system_prompt}]
    # 取最近6轮对话（12条消息）作为记忆
    recent = conversation_history[-12:] if len(conversation_history) > 12 else conversation_history
    messages.extend(recent)
    messages.append({"role": "user", "content": text})

    ai_reply = ""
    try:
        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }
        data = {
            "model": "deepseek-chat",
            "messages": messages
        }
        resp = requests.post("https://api.deepseek.com/chat/completions", headers=headers, json=data, timeout=15)
        if resp.status_code == 200:
            ai_reply = resp.json()["choices"][0]["message"]["content"]
        else:
            ai_reply = f"我听到你说：{text}。不好意思，AI暂时休息了，我们直接来聊聊吧～"
    except Exception:
        ai_reply = f"我听到你说：{text}。不好意思，AI暂时休息了，我们直接来聊聊吧～"

    # 保存本轮对话到记忆（最多保留50轮100条）
    conversation_history.append({"role": "user", "content": text})
    conversation_history.append({"role": "assistant", "content": ai_reply})
    if len(conversation_history) > 100:
        conversation_history[:50] = []

    return jsonify({
        "reply": ai_reply,
        "command": "",
        "action": "talk"
    })


# 抽奖接口：一次抽取N名未中奖同学
@app.route('/api/lottery', methods=['POST'])
def lottery():
    global awarded

    draw_n = request.json.get('count', None)
    if draw_n is None:
        draw_n = draw_count

    available = [s for s in students if s["id"] not in awarded]

    if not available or len(available) < draw_n:
        awarded = []
        available = [s for s in students]

    actual_n = min(draw_n, len(available))
    winners = random.sample(available, actual_n)
    for w in winners:
        awarded.append(w["id"])

    return jsonify({
        "winners": winners,
        "count": actual_n,
        "drawCount": draw_count,
        "totalAwarded": len(awarded),
        "totalStudents": len(students)
    })


# 获取已/未抽取状态
@app.route('/api/status', methods=['GET'])
def status():
    return jsonify({
        "awarded": awarded,
        "drawCount": draw_count,
        "totalStudents": len(students),
        "remaining": len(students) - len(awarded)
    })


# 重置抽奖
@app.route('/api/reset', methods=['POST'])
def reset_lottery():
    global awarded
    awarded = []
    return jsonify({
        "awarded": awarded,
        "remaining": len(students)
    })


# ==================== Edge TTS 语音合成（微软晓晓，自然中文） ====================
import importlib.util

EDGE_TTS_VOICE = 'zh-CN-XiaoxiaoNeural'
edge_tts_available = importlib.util.find_spec('edge_tts') is not None

if edge_tts_available:
    import edge_tts
    import asyncio

@app.route('/api/tts', methods=['POST'])
def text_to_speech():
    text = request.json.get('text', '').strip()
    if not text:
        return jsonify({'error': 'no text'}), 400

    filename = hashlib.md5(text.encode()).hexdigest() + '.mp3'
    filepath = os.path.join(AUDIO_DIR, filename)

    if not os.path.exists(filepath):
        generated = False

        # 方案1: Edge TTS（如果可用）
        if edge_tts_available:
            try:
                asyncio.run(edge_tts.Communicate(
                    text,
                    voice=EDGE_TTS_VOICE,
                    rate='+10%',
                    pitch='+0Hz'
                ).save(filepath))
                generated = True
            except Exception as e:
                print(f"Edge TTS error: {e}")

        # 方案2: fallback到macOS say
        if not generated:
            try:
                fallback = filepath.rsplit('.', 1)[0] + '.aiff'
                subprocess.run([
                    'say', '-v', 'Tingting',
                    '-r', '175',
                    '-o', fallback,
                    text
                ], check=True, capture_output=True, timeout=10)
                return send_from_directory(AUDIO_DIR, os.path.basename(fallback), mimetype='audio/x-aiff')
            except Exception as e2:
                return jsonify({'error': str(e2)}), 500

    return send_from_directory(AUDIO_DIR, filename, mimetype='audio/mpeg')


@app.route('/api/tts/cleanup', methods=['POST'])
def cleanup_audio():
    now = time.time()
    count = 0
    for f in os.listdir(AUDIO_DIR):
        fp = os.path.join(AUDIO_DIR, f)
        if os.path.isfile(fp) and now - os.path.getmtime(fp) > 3600:
            os.remove(fp)
            count += 1
    return jsonify({'cleaned': count})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
