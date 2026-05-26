#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
全链路 MiniMax 数据生成脚本
所有数据（书籍信息、内容简介、金句、内容解析、字幕）全部通过 MiniMax API 生成
无需任何外部爬虫，一条命令搞定全部数据

使用方法:
  python minimax_pipeline.py                   # 生成10本数据并导入云数据库
  python minimax_pipeline.py --count 5         # 只生成5本
  python minimax_pipeline.py --skip-import      # 跳过导入，只生成数据
  python minimax_pipeline.py --books "小王子,活着" # 只生成指定书籍
  python minimax_pipeline.py --resume           # 从断点续传
"""

import os
import re
import sys
import json
import time
import logging
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

# 路径配置
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data_source"
SCRIPTS_DIR = DATA_DIR / "scripts"
PROGRESS_FILE = DATA_DIR / "pipeline_progress.json"

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)


# ==================== 10本精选书单 ====================
DEFAULT_BOOKS = [
    "小王子",
    "活着",
    "三体",
    "百年孤独",
    "平凡的世界",
    "追风筝的人",
    "解忧杂货店",
    "人类简史",
    "红楼梦",
    "围城",
]

# ==================== 分类系统 ====================
CATEGORY_MAP = {
    1: "经典名著", 2: "儿童文学", 3: "科普百科",
    4: "历史传记", 5: "哲学心理", 6: "文学小说",
    7: "诗词歌赋", 8: "家庭教育", 9: "成长励志",
    10: "科幻悬疑", 11: "散文随笔", 12: "其他"
}

CATEGORY_KEYWORDS = {
    1: ["名著", "经典", "四大名著", "红楼梦", "三国", "水浒", "西游"],
    2: ["儿童", "童话", "绘本", "少年", "小王子", "小豆豆"],
    3: ["科普", "百科", "科学", "宇宙", "物理", "化学", "十万个"],
    4: ["历史", "传记", "史记", "人物", "帝王", "朝代"],
    5: ["哲学", "心理", "思维", "逻辑", "禅", "冥想", "瓦尔登湖"],
    6: ["小说", "文学", "故事", "虚构", "余华", "路遥", "莫言"],
    7: ["诗词", "诗歌", "唐诗", "宋词", "诗经", "古文"],
    8: ["教育", "家庭", "育儿", "管教", "妈妈", "亲子"],
    9: ["励志", "成长", "奋斗", "成功", "钢铁"],
    10: ["科幻", "悬疑", "推理", "三体", "东野", "侦探"],
    11: ["散文", "随笔", "杂文", "游记", "三毛", "鲁迅"],
    12: ["其他"]
}

CATEGORY_COLORS = {
    1: "#8B4513", 2: "#FF6B6B", 3: "#4ECDC4",
    4: "#9B59B6", 5: "#3498DB", 6: "#E74C3C",
    7: "#F39C12", 8: "#27AE60", 9: "#1ABC9C",
    10: "#2C3E50", 11: "#E67E22", 12: "#95A5A6"
}


def auto_classify(title: str, author: str = "", description: str = "") -> tuple:
    """根据书名/作者/简介自动推断分类"""
    text = f"{title} {author} {description}"
    for cat_id, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                return cat_id, CATEGORY_MAP[cat_id]
    return 12, "其他"


def generate_cover_color(title: str) -> str:
    """根据书名生成封面背景色"""
    cat_id, _ = auto_classify(title)
    return CATEGORY_COLORS.get(cat_id, "#95A5A6")


# ==================== MiniMax API 客户端 ====================
class MiniMaxClient:
    """MiniMax API 客户端 - 统一入口，所有数据生成走此客户端"""

    def __init__(self, api_key: str, base_url: str = "https://api.minimaxi.com/anthropic"):
        self.api_key = api_key
        self.base_url = base_url
        self.model = "MiniMax-M2.5-highspeed"

        try:
            from anthropic import Anthropic
            self.client = Anthropic(api_key=api_key, base_url=base_url)
            logger.info("✅ MiniMax 客户端初始化成功（anthropic库）")
        except ImportError:
            self.client = None
            logger.warning("⚠️ 未安装 anthropic 库，将使用 httpx 降级方案")

    def chat(self, system_prompt: str, user_prompt: str, max_tokens: int = 8000,
             temperature: float = 0.7) -> str:
        """统一调用接口"""
        if self.client:
            return self._chat_anthropic(system_prompt, user_prompt, max_tokens, temperature)
        else:
            return self._chat_httpx(system_prompt, user_prompt, max_tokens, temperature)

    def _chat_anthropic(self, system_prompt: str, user_prompt: str,
                        max_tokens: int, temperature: float) -> str:
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}]
            )
            # MiniMax 可能返回 thinking + text 两种 block，只取 text
            for block in response.content:
                if block.type == "text":
                    return block.text
            # 如果没有 text block，取最后一个 block 的文本
            if response.content:
                last = response.content[-1]
                if hasattr(last, 'text'):
                    return last.text
            raise ValueError("API 返回中未找到文本内容")
        except Exception as e:
            logger.error(f"MiniMax API 调用失败: {e}")
            raise

    def _chat_httpx(self, system_prompt: str, user_prompt: str,
                    max_tokens: int, temperature: float) -> str:
        import httpx

        headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01"
        }

        payload = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}]
        }

        with httpx.Client(timeout=180.0) as client:
            response = client.post(
                f"{self.base_url}/messages",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            result = response.json()
            return result["content"][0]["text"]


# ==================== 数据生成步骤 ====================

def generate_book_info(client: MiniMaxClient, title: str) -> Dict:
    """
    步骤1：通过 MiniMax API 生成书籍基础信息
    包含：作者、出版社、ISBN、简介、分类等
    """
    system_prompt = """你是一位资深的图书编辑和数据库专家。你的任务是根据书名提供准确的书籍基础信息。
请严格按照JSON格式输出，不要添加任何多余的文字或markdown标记。"""

    user_prompt = f"""请为《{title}》这本书提供基础信息，严格按照以下JSON格式输出：

{{
    "title": "{title}",
    "author": "作者全名",
    "category": 分类ID(1-12的数字),
    "categoryName": "分类名称",
    "publisher": "出版社",
    "isbn": "ISBN编号",
    "publishDate": "出版年份",
    "pages": 页数,
    "description": "200-300字的书籍内容简介，要包含书籍的核心主题、文学地位和影响力",
    "coverColor": "根据书籍分类选择合适的颜色代码"
}}

分类ID对照：
1=经典名著, 2=儿童文学, 3=科普百科, 4=历史传记, 5=哲学心理, 6=文学小说,
7=诗词歌赋, 8=家庭教育, 9=成长励志, 10=科幻悬疑, 11=散文随笔, 12=其他

要求：
- 作者名必须是真实准确的
- ISBN格式正确
- 简介要全面、有深度，200-300字
- 只输出JSON，不要任何其他文字"""

    logger.info(f"  📡 调用API获取《{title}》基础信息...")

    raw = client.chat(system_prompt, user_prompt, max_tokens=2000, temperature=0.3)

    # 解析JSON
    try:
        # 清理markdown标记
        raw = re.sub(r'```json\s*', '', raw)
        raw = re.sub(r'```\s*', '', raw)
        raw = raw.strip()

        info = json.loads(raw)

        # 确保必要字段
        info["title"] = title
        info.setdefault("author", "未知作者")
        info.setdefault("publisher", "")
        info.setdefault("isbn", "")
        info.setdefault("publishDate", "")
        info.setdefault("pages", 0)
        info.setdefault("description", "")

        # 确保分类正确
        if "category" not in info or not isinstance(info["category"], int):
            cat_id, cat_name = auto_classify(title, info.get("author", ""), info.get("description", ""))
            info["category"] = cat_id
            info["categoryName"] = cat_name
        else:
            info["categoryName"] = CATEGORY_MAP.get(info["category"], "其他")

        # 封面颜色
        info["coverColor"] = CATEGORY_COLORS.get(info["category"], "#95A5A6")

        logger.info(f"  ✅ 基础信息: {info['author']} / {info['publisher']} / {info['categoryName']}")
        return info

    except json.JSONDecodeError as e:
        logger.warning(f"  ⚠️ JSON解析失败，使用关键词匹配分类: {e}")
        cat_id, cat_name = auto_classify(title)
        return {
            "title": title,
            "author": "未知作者",
            "category": cat_id,
            "categoryName": cat_name,
            "publisher": "",
            "isbn": "",
            "publishDate": "",
            "pages": 0,
            "description": "",
            "coverColor": CATEGORY_COLORS.get(cat_id, "#95A5A6"),
        }


def generate_script_and_quotes(client: MiniMaxClient, title: str, author: str,
                                 description: str = "") -> Dict:
    """
    步骤2：生成朗读文稿 + 金句（一次API调用完成）
    """
    system_prompt = """你是一位资深文学解读专家和有声书制作人。你擅长将经典文学作品用温暖、亲切、富有感染力的语言讲解给听众。
你的声音仿佛在和朋友聊天，自然流畅，引人入胜。生成的文稿将用于TTS朗读，所以语言必须口语化、适合听。"""

    desc_section = f"\n书籍简介（供参考）：{description}" if description else ""

    user_prompt = f"""请为《{title}》（作者：{author}）生成一篇约15-18分钟的深度解读文稿，目标字数约4500字。

{desc_section}

请严格按以下结构写作，每个部分之间用空行分隔：

【开篇引入】（约300字）
介绍书籍地位、获奖情况、全球影响力，用温暖亲切的语气开场

【时代背景】（约500字）
作者生平、创作背景、所处的社会环境

【故事梗概】（约800字）
清晰讲述全书主线剧情，不剧透关键结局

【核心人物分析】（约1000字）
深度解析3-4个主要人物的性格与命运

【核心主题解读】（约1200字）
剖析书籍传递的核心思想与价值观，联系现实生活

【经典赏析】（约400字）
赏析书中2-3个精彩片段

【结尾升华】（约300字）
总结书籍的现实意义与启示

【朗读提示】
- 语言口语化，适合音频朗读，避免过于学术化
- 每段结束后标注[停顿1秒]
- 重要观点前标注[强调]
- 书名用《》括起来
- 纯文本输出，不要任何markdown格式（不要#、**等）

======金句部分======
在文稿末尾另起一行写"=====金句====="，然后列出本书最经典的8条金句，每条不超过50字，格式：
"金句内容" —— 出处

注意：金句部分与文稿部分用"=====金句====="分隔，便于程序解析。"""

    logger.info(f"  📡 调用API生成《{title}》文稿+金句...")

    raw = client.chat(system_prompt, user_prompt, max_tokens=8000, temperature=0.7)

    # 解析：分离文稿和金句
    parts = re.split(r'=====金句=====', raw, maxsplit=1)
    script = parts[0].strip() if parts else raw.strip()
    quotes_text = parts[1].strip() if len(parts) > 1 else ""

    # 清理文稿中的markdown标记
    script = re.sub(r'```[\s\S]*?```', '', script)
    script = re.sub(r'#{1,6}\s+', '', script)
    script = re.sub(r'\*{1,2}([^*]+)\*{1,2}', r'\1', script)
    script = re.sub(r'\n{3,}', '\n\n', script)
    script = script.strip()

    # 提取金句列表
    quotes = []
    if quotes_text:
        for line in quotes_text.split('\n'):
            line = line.strip()
            if not line:
                continue
            # 匹配 "金句" —— 出处 格式
            q_match = re.match(r'["""\u201c\u201d](.+?)["""\u201c\u201d]\s*(?:——|—)\s*(.+)', line)
            if q_match:
                quotes.append({
                    "content": q_match.group(1),
                    "source": q_match.group(2)
                })
            elif 10 <= len(line) <= 60 and '。' in line:
                quotes.append({"content": line, "source": ""})

    # 统计中文字数
    char_count = len(re.findall(r'[\u4e00-\u9fa5]', script))

    logger.info(f"  ✅ 文稿: {char_count}字 | 金句: {len(quotes)}条")

    return {
        "script": script,
        "quotes": quotes,
        "quotesText": quotes_text,
        "charCount": char_count,
        "scriptSource": "minimax"
    }


def split_sentences(script: str) -> List[Dict]:
    """将文稿分割成句子数组，用于字幕同步播放"""
    raw_sentences = re.split(r'(?<=[。！？\n])', script)

    sentences = []
    for s in raw_sentences:
        s = s.strip()
        if not s or len(s) < 2:
            continue

        # 处理[停顿]标记
        pause_match = re.match(r'\[停顿(\d+)秒?\]', s)
        if pause_match:
            if sentences:
                sentences[-1]["text"] += f" [停顿{pause_match.group(1)}秒]"
            continue

        # 处理[强调]标记
        s = s.replace('[强调]', '')

        sentences.append({
            "text": s,
            "startTime": 0,
            "endTime": 0
        })

    return sentences


# ==================== 进度管理 ====================

def load_progress() -> Dict:
    """加载进度文件"""
    if PROGRESS_FILE.exists():
        try:
            with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {"completed": [], "failed": [], "books_data": []}


def save_progress(progress: Dict):
    """保存进度文件"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)


# ==================== 云数据库导入 ====================

def import_to_cloud(books: List[Dict], quotes: List[Dict]) -> Dict:
    """导入数据到微信云开发数据库"""
    app_id = os.getenv("WECHAT_APP_ID", "")
    secret = os.getenv("WECHAT_SECRET", "")
    env_id = os.getenv("WECHAT_ENV_ID", "cloud1-d2ggs9k1bf3aa2a18")

    if not app_id or not secret:
        logger.warning("⚠️ 未配置 WECHAT_APP_ID 或 WECHAT_SECRET")
        logger.info("请手动导入数据到云开发控制台")
        return {"success": False, "error": "未配置微信云开发参数"}

    try:
        from modules.cloud_import import WeChatCloudImporter

        importer = WeChatCloudImporter(app_id=app_id, secret=secret, env_id=env_id)

        # 获取 access_token
        if not importer.get_access_token():
            logger.error("❌ 获取 access_token 失败")
            return {"success": False, "error": "获取access_token失败"}

        # 导入 books
        logger.info(f"📚 导入 {len(books)} 本书到 books 集合...")
        books_result = importer.batch_import(books)

        # 导入 quotes
        if quotes:
            logger.info(f"💬 导入 {len(quotes)} 条金句到 quotes 集合...")
            quotes_result = importer.call_cloud_function("batchImportBooks", {
                "action": "importQuotes",
                "data": quotes
            })

        return {
            "success": True,
            "books_result": books_result,
            "quotes_count": len(quotes)
        }

    except ImportError:
        logger.error("❌ 无法导入 cloud_import 模块")
        return {"success": False, "error": "模块导入失败"}
    except Exception as e:
        logger.error(f"❌ 导入异常: {e}")
        return {"success": False, "error": str(e)}


# ==================== 环境变量加载 ====================

def load_env():
    """加载环境变量"""
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        with open(env_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    value = value.strip()
                    # 处理 ${VAR} 格式
                    if value.startswith('${') and value.endswith('}'):
                        ref_key = value[2:-1]
                        value = os.getenv(ref_key, "")
                    os.environ.setdefault(key.strip(), value)

    # 从根目录 .env
    root_env = Path(__file__).parent.parent / ".env"
    if root_env.exists():
        with open(root_env, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    value = value.strip()
                    if value.startswith('${') and value.endswith('}'):
                        ref_key = value[2:-1]
                        value = os.getenv(ref_key, "")
                    os.environ.setdefault(key.strip(), value)


# ==================== 主流程 ====================

def main():
    parser = argparse.ArgumentParser(
        description="听书小程序 - 全链路 MiniMax 数据生成工具",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--count", type=int, default=10, help="生成书籍数量（默认10）")
    parser.add_argument("--skip-import", action="store_true", help="跳过云数据库导入")
    parser.add_argument("--skip-tts", action="store_true", help="跳过 TTS 音频生成")
    parser.add_argument("--tts-only", type=str, help="只对指定书籍生成 TTS（逗号分隔），跳过 AI 文稿生成")
    parser.add_argument("--books", type=str, help="指定书名，逗号分隔")
    parser.add_argument("--voice", type=str, default="zh-CN-YunxiNeural", help="TTS 声音（默认 zh-CN-YunxiNeural）")
    parser.add_argument("--tts-rate", type=str, default="-5%", help="TTS 语速（默认 -5%%）")
    parser.add_argument("--tts-pitch", type=str, default="-2Hz", help="TTS 音调（默认 -2Hz）")
    parser.add_argument("--resume", action="store_true", help="从断点续传")
    parser.add_argument("--retry-failed", action="store_true", help="重试失败的书籍")
    parser.add_argument("--upload-cloud", action="store_true", help="TTS 生成后上传到云存储并更新数据库")
    args = parser.parse_args()

    # 加载环境变量
    load_env()

    # 检查API Key
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    base_url = os.getenv("ANTHROPIC_BASE_URL", "https://api.minimaxi.com/anthropic")

    if not api_key:
        logger.error("❌ 未配置 ANTHROPIC_API_KEY")
        logger.info("请在 pipeline/.env 或根目录 .env 中设置: ANTHROPIC_API_KEY=你的密钥")
        sys.exit(1)

    # 初始化客户端
    client = MiniMaxClient(api_key, base_url)

    # 确定书单
    if args.books:
        book_names = [b.strip() for b in args.books.split(",") if b.strip()]
    else:
        book_names = DEFAULT_BOOKS[:args.count]

    # 确保输出目录
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)

    # 加载进度
    progress = load_progress() if args.resume else {"completed": [], "failed": [], "books_data": []}

    completed_set = set(progress["completed"])
    failed_list = progress.get("failed", [])

    # 如果是重试失败
    if args.retry_failed and failed_list:
        book_names = failed_list
        logger.info(f"🔄 重试 {len(failed_list)} 本失败的书籍")

    print(f"""
╔══════════════════════════════════════════════════════════╗
║                                                          ║
║     📚 听书小程序 - 全链路 MiniMax 数据生成 v3.1          ║
║                                                          ║
║     🤖 所有数据由 AI 一站式生成，无需爬虫                  ║
║     🎙️  Edge-TTS 音频合成 + 字幕时间戳                   ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝

📋 待处理: {len(book_names)} 本书
📡 API: MiniMax ({base_url})
🎙️  TTS: {args.voice}
""")
    start_time = time.time()
    now = int(time.time() * 1000)

    # ==================== TTS-ONLY 模式 ====================
    # 如果指定了 --tts-only，跳过 AI 文稿生成，直接对已有文稿生成音频
    if args.tts_only:
        tts_book_names = [b.strip() for b in args.tts_only.split(",") if b.strip()]
        logger.info(f"🎙️ TTS-ONLY 模式: 对 {len(tts_book_names)} 本书生成音频")

        # 尝试导入 edge_tts_generator
        try:
            from edge_tts_generator import EdgeTTSGenerator
        except ImportError as e:
            logger.error(f"❌ 无法导入 edge_tts_generator: {e}")
            logger.info("请先安装依赖: pip install edge-tts")
            sys.exit(1)

        tts_gen = EdgeTTSGenerator(voice=args.voice, rate=args.tts_rate, pitch=args.tts_pitch)
        audios_dir = Path(__file__).parent / "output" / "audios"
        subs_dir = Path(__file__).parent / "output" / "subtitles"
        audios_dir.mkdir(parents=True, exist_ok=True)
        subs_dir.mkdir(parents=True, exist_ok=True)

        # 云存储上传器（可选）
        uploader = None
        if args.upload_cloud:
            try:
                from modules.cloud_upload import CloudStorageUploader
                uploader = CloudStorageUploader()
            except Exception as e:
                logger.warning(f"⚠️ 云存储上传模块加载失败: {e}")

        tts_results = []
        for i, title in enumerate(tts_book_names):
            logger.info(f"\n{'═'*60}")
            logger.info(f"[{i+1}/{len(tts_book_names)}] 🎙️ 生成音频: 《{title}》")
            logger.info(f"{'═'*60}")

            # 查找已有文稿
            script_file = SCRIPTS_DIR / f"{title}_script.txt"
            book_json_file = DATA_DIR / f"{title}_book.json"

            script_text = ""
            if script_file.exists():
                with open(script_file, 'r', encoding='utf-8') as f:
                    script_text = f.read()
            elif book_json_file.exists():
                with open(book_json_file, 'r', encoding='utf-8') as f:
                    book_data = json.load(f)
                    script_text = book_data.get("script", "")
            else:
                # 尝试从 step4 数据中查找
                books_file = DATA_DIR / "step4_for_database_import.json"
                if books_file.exists():
                    with open(books_file, 'r', encoding='utf-8') as f:
                        books_data = json.load(f)
                    for book in books_data:
                        if book.get("title") == title:
                            script_text = book.get("script", "")
                            break

            if not script_text.strip():
                logger.error(f"  ❌ 未找到《{title}》的文稿，跳过")
                continue

            mp3_path = str(audios_dir / f"{title}.mp3")
            vtt_path = str(subs_dir / f"{title}.vtt")

            try:
                result = tts_gen.generate(
                    text=script_text,
                    output_mp3=mp3_path,
                    output_vtt=vtt_path,
                    voice=args.voice,
                    rate=args.tts_rate,
                    pitch=args.tts_pitch,
                )

                tts_results.append({
                    "title": title,
                    "mp3": result["mp3"],
                    "vtt": result["vtt"],
                    "subtitles": result["subtitles"],
                    "duration_seconds": result["duration_seconds"],
                    "duration_text": f"{int(result['duration_seconds']//60):02d}:{int(result['duration_seconds']%60):02d}",
                })

                logger.info(f"  ✅ 音频生成成功: {result['duration_seconds']:.1f}s, {len(result['subtitles'])} 句字幕")

                # 上传到云存储
                if uploader:
                    logger.info(f"  ☁️ 上传到云存储...")
                    upload_result = uploader.upload_book_assets(title, mp3_path, vtt_path)

                    # 更新数据库
                    if upload_result.get("audioUrl"):
                        logger.info(f"  📝 更新云数据库...")
                        uploader.update_book_audio_fields(
                            title,
                            audio_url=upload_result["audioUrl"],
                            subtitle_url=upload_result.get("subtitleUrl", ""),
                            subtitles_json=result["subtitles"],
                            audio_duration=result["duration_seconds"],
                        )

            except Exception as e:
                logger.error(f"  ❌ 音频生成失败: {e}")

        # 保存 TTS 结果
        tts_output = DATA_DIR / "tts_results.json"
        with open(tts_output, 'w', encoding='utf-8') as f:
            json.dump(tts_results, f, ensure_ascii=False, indent=2)

        print(f"\n{'═'*60}")
        print(f"🎙️ TTS 生成完成！成功 {len(tts_results)}/{len(tts_book_names)} 本")
        print(f"{'═'*60}")
        for r in tts_results:
            print(f"  📖 《{r['title']}》: {r['duration_text']} ({len(r['subtitles'])} 句字幕)")
        print(f"\n📂 输出: {tts_output}")
        return

    # ==================== 逐本生成 ====================
    all_books = list(progress.get("books_data", []))
    all_quotes = []

    for i, title in enumerate(book_names):
        # 跳过已完成的
        if title in completed_set and not args.retry_failed:
            logger.info(f"[{i+1}/{len(book_names)}] ⏭️ 已完成，跳过: 《{title}》")
            continue

        logger.info(f"\n{'═'*60}")
        logger.info(f"[{i+1}/{len(book_names)}] 📖 开始处理: 《{title}》")
        logger.info(f"{'═'*60}")

        try:
            # 步骤1：生成书籍基础信息
            logger.info(f"\n  [步骤1/2] 生成基础信息...")
            info = generate_book_info(client, title)

            # 步骤2：生成文稿+金句（一次调用）
            logger.info(f"\n  [步骤2/2] 生成文稿+金句...")
            script_data = generate_script_and_quotes(
                client, title,
                info.get("author", ""),
                info.get("description", "")
            )

            # 分句
            sentences = split_sentences(script_data["script"])

            # 组装完整数据
            book_record = {
                # 基础信息
                "title": title,
                "author": info.get("author", "未知作者"),
                "category": info.get("category", 12),
                "categoryName": info.get("categoryName", "其他"),
                "publisher": info.get("publisher", ""),
                "isbn": info.get("isbn", ""),
                "publishDate": info.get("publishDate", ""),
                "pages": info.get("pages", 0),
                "description": info.get("description", ""),
                "coverColor": info.get("coverColor", "#95A5A6"),
                "coverUrl": "",

                # 字幕/文稿
                "script": script_data["script"],
                "scriptLength": script_data["charCount"],
                "scriptSource": script_data["scriptSource"],
                "scriptVersion": 1,
                "sentences": sentences,

                # 音频（待生成）
                "audioUrl": "",
                "audioDuration": 0,
                "audioDurationText": "",
                "isAudioGenerated": False,
                "ttsVoice": "zh-CN-YunxiNeural",
                "ttsRate": "-10%",
                "ttsPitch": "-5Hz",

                # 状态
                "isHot": i < 3,
                "isGenerated": True,
                "isPublished": False,
                "viewCount": 0,
                "playCount": 0,

                # 质量
                "qualityScore": 0,
                "qualityNote": "",

                # 时间
                "createTime": now,
                "updateTime": now,

                # 来源
                "source": "minimax",
                "sourceUrl": "",
                "crawlTime": now,
                "importedBooks": f"minimax_{datetime.now().strftime('%Y%m%d_%H%M')}",
            }

            # 保存单独文件
            script_file = SCRIPTS_DIR / f"{title}_script.txt"
            with open(script_file, 'w', encoding='utf-8') as f:
                f.write(script_data["script"])

            quotes_file = SCRIPTS_DIR / f"{title}_quotes.txt"
            with open(quotes_file, 'w', encoding='utf-8') as f:
                f.write(script_data["quotesText"])

            all_books.append(book_record)

            # 生成 quotes 集合数据
            for q in script_data["quotes"]:
                all_quotes.append({
                    "content": q.get("content", ""),
                    "author": info.get("author", ""),
                    "bookName": title,
                    "categoryName": info.get("categoryName", "其他"),
                    "playCount": 0,
                    "likeCount": 0,
                    "createTime": now,
                    "updateTime": now,
                })

            # ========== 步骤3（可选）：TTS 音频 + 字幕生成 ==========
            if not args.skip_tts:
                try:
                    from edge_tts_generator import EdgeTTSGenerator

                    audios_dir = Path(__file__).parent / "output" / "audios"
                    subs_dir = Path(__file__).parent / "output" / "subtitles"
                    audios_dir.mkdir(parents=True, exist_ok=True)
                    subs_dir.mkdir(parents=True, exist_ok=True)

                    logger.info(f"\n  [步骤3] 🎙️ 生成音频 + 字幕...")
                    tts_gen = EdgeTTSGenerator(voice=args.voice, rate=args.tts_rate, pitch=args.tts_pitch)

                    tts_result = tts_gen.generate(
                        text=script_data["script"],
                        output_mp3=str(audios_dir / f"{title}.mp3"),
                        output_vtt=str(subs_dir / f"{title}.vtt"),
                    )

                    # 更新 book_record
                    book_record["audioUrl"] = f"output/audios/{title}.mp3"
                    book_record["subtitleUrl"] = f"output/subtitles/{title}.vtt"
                    book_record["subtitles"] = tts_result["subtitles"]
                    book_record["audioDuration"] = tts_result["duration_seconds"]
                    book_record["audioDurationText"] = f"{int(tts_result['duration_seconds']//60):02d}:{int(tts_result['duration_seconds']%60):02d}"
                    book_record["isAudioGenerated"] = True

                    logger.info(f"     ✅ 音频: {tts_result['duration_seconds']:.1f}s | 字幕: {len(tts_result['subtitles'])} 句")

                    # 上传到云存储（可选）
                    if args.upload_cloud:
                        try:
                            from modules.cloud_upload import CloudStorageUploader
                            uploader = CloudStorageUploader()
                            upload_res = uploader.upload_book_assets(
                                title,
                                mp3_path=str(audios_dir / f"{title}.mp3"),
                                vtt_path=str(subs_dir / f"{title}.vtt"),
                            )
                            if upload_res.get("audioUrl"):
                                book_record["audioUrl"] = upload_res["audioUrl"]
                                book_record["subtitleUrl"] = upload_res.get("subtitleUrl", "")
                                uploader.update_book_audio_fields(
                                    title,
                                    audio_url=upload_res["audioUrl"],
                                    subtitle_url=upload_res.get("subtitleUrl", ""),
                                    subtitles_json=tts_result["subtitles"],
                                    audio_duration=tts_result["duration_seconds"],
                                )
                                logger.info(f"     ☁️ 已上传到云存储并更新数据库")
                        except Exception as e:
                            logger.warning(f"     ⚠️ 云存储上传失败: {e}")

                except ImportError:
                    logger.warning("  ⚠️ edge-tts 未安装，跳过音频生成（pip install edge-tts）")
                except Exception as e:
                    logger.error(f"  ⚠️ TTS 生成失败: {e}")

            # 更新进度
            progress["completed"].append(title)
            if title in progress.get("failed", []):
                progress["failed"].remove(title)
            progress["books_data"] = all_books
            save_progress(progress)

            logger.info(f"\n  🎉 《{title}》处理完成！")
            logger.info(f"     📝 文稿: {script_data['charCount']}字, {len(sentences)}句")
            logger.info(f"     💬 金句: {len(script_data['quotes'])}条")
            logger.info(f"     📂 文件: {script_file.name}")

        except Exception as e:
            logger.error(f"  ❌ 《{title}》处理失败: {e}")
            if title not in progress.get("failed", []):
                progress.setdefault("failed", []).append(title)
            save_progress(progress)

        # API 调用间隔
        if i < len(book_names) - 1:
            delay = 3
            logger.info(f"  ⏳ 等待{delay}秒...")
            time.sleep(delay)

    # ==================== 保存最终数据 ====================
    elapsed = time.time() - start_time

    # 保存 books 数据
    books_output = DATA_DIR / "step4_for_database_import.json"
    with open(books_output, 'w', encoding='utf-8') as f:
        json.dump(all_books, f, ensure_ascii=False, indent=2)

    # 保存 quotes 数据
    quotes_output = DATA_DIR / "quotes_for_database_import.json"
    with open(quotes_output, 'w', encoding='utf-8') as f:
        json.dump(all_quotes, f, ensure_ascii=False, indent=2)

    # 保存完整中间数据
    full_output = DATA_DIR / "full_data_with_script.json"
    with open(full_output, 'w', encoding='utf-8') as f:
        json.dump(all_books, f, ensure_ascii=False, indent=2)

    # ==================== 汇总 ====================
    print(f"\n{'═'*60}")
    print(f"🎉 数据生成完成！耗时: {elapsed:.1f}秒")
    print(f"{'═'*60}")
    print(f"\n📊 生成结果:")
    print(f"   ✅ 成功: {len(all_books)} 本")
    print(f"   ❌ 失败: {len(progress.get('failed', []))} 本")
    print(f"   💬 金句: {len(all_quotes)} 条")
    print(f"\n📂 输出文件:")
    print(f"   📄 books数据: {books_output}")
    print(f"   📄 quotes数据: {quotes_output}")
    print(f"   📄 完整数据: {full_output}")
    print(f"   📁 文稿目录: {SCRIPTS_DIR}/")

    # 打印每本书的摘要
    print(f"\n📚 书籍摘要:")
    for b in all_books:
        audio_info = f"音频: {b['audioDurationText']}" if b.get("isAudioGenerated") else "音频: 未生成"
        sub_info = f"字幕: {len(b.get('subtitles', []))}句" if b.get("subtitles") else "字幕: 无"
        print(f"   📖 《{b['title']}》- {b['author']} [{b['categoryName']}]")
        print(f"      文稿: {b['scriptLength']}字 | 句数: {len(b['sentences'])} | {audio_info} | {sub_info} | 热门: {'是' if b['isHot'] else '否'}")

    # ==================== 导入云数据库 ====================
    if not args.skip_import and all_books:
        print(f"\n{'═'*60}")
        print(f"☁️ 开始导入云数据库...")
        print(f"{'═'*60}")

        result = import_to_cloud(all_books, all_quotes)

        if result.get("success"):
            print(f"\n🎉 导入完成！")
        else:
            print(f"\n⚠️ 自动导入失败: {result.get('error', '未知错误')}")
            print(f"\n📋 请手动导入:")
            print(f"   1. 打开微信开发者工具 → 云开发控制台")
            print(f"   2. 创建 books 和 quotes 集合（如果不存在）")
            print(f"   3. books 集合 → 导入 → 选择: {books_output}")
            print(f"   4. quotes 集合 → 导入 → 选择: {quotes_output}")
    elif args.skip_import:
        print(f"\n⏭️ 已跳过云数据库导入")
        print(f"\n📋 手动导入步骤:")
        print(f"   1. 打开微信开发者工具 → 云开发控制台")
        print(f"   2. 创建 books 和 quotes 集合（如果不存在）")
        print(f"   3. books 集合 → 导入 → 选择: {books_output}")
        print(f"   4. quotes 集合 → 导入 → 选择: {quotes_output}")
        print(f"\n💡 或运行: python minimax_pipeline.py --resume（跳过已完成的，直接导入）")


if __name__ == "__main__":
    main()
