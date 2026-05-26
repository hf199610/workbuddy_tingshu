#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
字幕文稿生成脚本
支持：MiniMax API / 豆包API 双模式
生成约4500字朗读文稿 + 8条金句

使用方法:
  python generate_scripts.py --input crawled_output.json       # 从爬取结果生成
  python generate_scripts.py --books "小王子,活着"              # 指定书名
  python generate_scripts.py --input step4_for_database_import.json  # 补生成缺失文稿
  python generate_scripts.py --api minimax                     # 指定使用MiniMax
  python generate_scripts.py --api doubao                      # 指定使用豆包
  python generate_scripts.py --dry-run                         # 预览模式（不调用API）

输出:
  - 每本书的文稿保存到 data_source/scripts/{书名}_script.txt
  - 金句保存到 data_source/scripts/{书名}_quotes.txt
  - 完整数据更新到输入JSON文件的 script/quotes/sentences 字段
"""

import os
import re
import sys
import json
import time
import logging
import argparse
from pathlib import Path
from typing import List, Dict, Optional

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)

# ==================== 路径配置 ====================
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data_source"
SCRIPTS_DIR = DATA_DIR / "scripts"

# ==================== Prompt模板 ====================
SCRIPT_PROMPT = """你是一位资深文学解读专家，请为《{title}》生成一篇约15-18分钟的深度解读文稿，目标字数约4500字，严格按照以下结构写作：

## 开篇引入（300字）
介绍书籍地位、获奖情况、全球影响力，用温暖亲切的语气开场

## 时代背景（500字）
作者生平、创作背景、所处的社会环境，为听众构建时代画面

## 故事梗概（800字）
清晰讲述全书主线剧情，不剧透关键结局，用生动的语言描绘故事脉络

## 核心人物分析（1000字）
深度解析3-4个主要人物的性格与命运，让听众理解人物动机

## 核心主题解读（1200字）
剖析书籍传递的核心思想与价值观，联系现实生活，引发思考

## 经典赏析（400字）
赏析书中2-3个精彩片段，展示文字之美

## 结尾升华（300字）
总结书籍的现实意义与对当代人的启示，留下温暖有力的结尾

【朗读提示】
- 语言口语化，适合音频朗读，避免过于学术化的表达
- 每段结束后标注[停顿1秒]
- 重要观点前标注[强调]
- 书籍名称和重要概念用《》括起来
- 不要出现任何markdown格式，纯文本输出

## 金句摘录
在文稿末尾，单独列出本书最经典的8条金句，每条不超过50字，格式：
"金句内容" —— 出处

{description_section}"""

DESCRIPTION_SECTION = """
## 背景补充
以下是书籍简介供参考：
{description}"""


# ==================== MiniMax API 客户端 ====================
class MiniMaxScriptGenerator:
    """使用 MiniMax API（Anthropic兼容格式）生成文稿"""

    def __init__(self, api_key: str, base_url: str = "https://api.minimaxi.com/anthropic"):
        self.api_key = api_key
        self.base_url = base_url
        self.model = "MiniMax-Text-01"

        try:
            from anthropic import Anthropic
            self.client = Anthropic(api_key=api_key, base_url=base_url)
            logger.info("✅ MiniMax 客户端初始化成功（anthropic库）")
        except ImportError:
            self.client = None
            logger.warning("⚠️ 未安装 anthropic 库，将使用 httpx 降级方案")

    def generate(self, title: str, author: str, description: str = "") -> Dict:
        """生成文稿和金句"""
        prompt = self._build_prompt(title, author, description)

        if self.client:
            return self._generate_with_anthropic(prompt)
        else:
            return self._generate_with_httpx(prompt)

    def _build_prompt(self, title: str, author: str, description: str) -> str:
        desc_section = ""
        if description:
            desc_section = DESCRIPTION_SECTION.format(description=description)

        return SCRIPT_PROMPT.format(
            title=title,
            author=author,
            description_section=desc_section
        )

    def _generate_with_anthropic(self, prompt: str) -> Dict:
        """使用 anthropic 库调用"""
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=8000,
                temperature=0.7,
                messages=[
                    {
                        "role": "system",
                        "content": "你是一位专业的文学解说员，擅长将复杂的文学作品用通俗易懂的语言讲解给听众。你的声音温暖而有磁性，语言生动有趣。"
                    },
                    {"role": "user", "content": prompt}
                ]
            )
            raw_text = response.content[0].text
            return self._parse_response(raw_text)
        except Exception as e:
            logger.error(f"MiniMax API 调用失败: {e}")
            raise

    def _generate_with_httpx(self, prompt: str) -> Dict:
        """使用 httpx 降级调用"""
        import httpx

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01"
        }

        payload = {
            "model": self.model,
            "max_tokens": 8000,
            "temperature": 0.7,
            "system": "你是一位专业的文学解说员，擅长将复杂的文学作品用通俗易懂的语言讲解给听众。你的声音温暖而有磁性，语言生动有趣。",
            "messages": [{"role": "user", "content": prompt}]
        }

        with httpx.Client(timeout=120.0) as client:
            response = client.post(
                f"{self.base_url}/messages",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            result = response.json()
            raw_text = result["content"][0]["text"]
            return self._parse_response(raw_text)

    def _parse_response(self, raw_text: str) -> Dict:
        """解析API返回，分离文稿和金句"""
        # 清理文本
        raw_text = re.sub(r'```[\s\S]*?```', '', raw_text)
        raw_text = re.sub(r'<!--[\s\S]*?-->', '', raw_text)
        raw_text = re.sub(r'\n{3,}', '\n\n', raw_text)

        # 分离金句
        parts = re.split(r'##\s*金句摘录|金句摘录', raw_text, maxsplit=1)
        script = parts[0].strip() if len(parts) > 1 else raw_text.strip()
        quotes_text = parts[1].strip() if len(parts) > 1 else ""

        # 提取金句列表
        quotes = []
        if quotes_text:
            for line in quotes_text.split('\n'):
                line = line.strip()
                # 匹配 "金句" 或 "金句" —— 出处 格式
                q_match = re.match(r'["""](.+?)["""]\s*(?:——|—)\s*(.+)', line)
                if q_match:
                    quotes.append({
                        "content": q_match.group(1),
                        "source": q_match.group(2)
                    })
                elif 10 <= len(line) <= 60 and '。' in line:
                    quotes.append({"content": line, "source": ""})

        # 统计中文字数
        chinese_chars = len(re.findall(r'[\u4e00-\u9fa5]', script))

        return {
            "script": script,
            "quotes": quotes,
            "quotesText": quotes_text,
            "charCount": chinese_chars,
            "scriptSource": "minimax"
        }


# ==================== 豆包 API 客户端 ====================
class DoubaoScriptGenerator:
    """使用豆包 API（火山引擎）生成文稿"""

    def __init__(self, api_key: str, base_url: str = "https://ark.cn-beijing.volces.com/api/v3",
                 model: str = "doubao-pro-32k"):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        logger.info(f"✅ 豆包客户端初始化成功（模型: {model}）")

    def generate(self, title: str, author: str, description: str = "") -> Dict:
        """使用豆包API生成文稿"""
        import httpx

        prompt = SCRIPT_PROMPT.format(
            title=title,
            author=author,
            description_section=DESCRIPTION_SECTION.format(description=description) if description else ""
        )

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "你是一位专业的文学解说员，擅长将复杂的文学作品用通俗易懂的语言讲解给听众。你的声音温暖而有磁性，语言生动有趣。"
                },
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 8000
        }

        with httpx.Client(timeout=120.0) as client:
            response = client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            result = response.json()

        raw_text = result["choices"][0]["message"]["content"]

        # 复用解析逻辑
        raw_text = re.sub(r'```[\s\S]*?```', '', raw_text)
        raw_text = re.sub(r'\n{3,}', '\n\n', raw_text)

        parts = re.split(r'##\s*金句摘录|金句摘录', raw_text, maxsplit=1)
        script = parts[0].strip() if len(parts) > 1 else raw_text.strip()
        quotes_text = parts[1].strip() if len(parts) > 1 else ""

        quotes = []
        if quotes_text:
            for line in quotes_text.split('\n'):
                line = line.strip()
                q_match = re.match(r'["""](.+?)["""]\s*(?:——|—)\s*(.+)', line)
                if q_match:
                    quotes.append({"content": q_match.group(1), "source": q_match.group(2)})
                elif 10 <= len(line) <= 60 and '。' in line:
                    quotes.append({"content": line, "source": ""})

        chinese_chars = len(re.findall(r'[\u4e00-\u9fa5]', script))

        return {
            "script": script,
            "quotes": quotes,
            "quotesText": quotes_text,
            "charCount": chinese_chars,
            "scriptSource": "doubao"
        }


# ==================== 句子分割 ====================
def split_sentences(script: str) -> List[Dict]:
    """
    将文稿分割成句子数组，用于字幕同步播放
    每个句子包含: text, startTime(待填充), endTime(待填充)
    """
    # 按句号/感叹号/问号/换行分割
    raw_sentences = re.split(r'(?<=[。！？\n])', script)

    sentences = []
    for s in raw_sentences:
        s = s.strip()
        if not s or len(s) < 2:
            continue

        # 处理[停顿]标记
        pause_match = re.match(r'\[停顿(\d+)秒?\]', s)
        if pause_match:
            # 如果是纯停顿标记，作为上一句的延伸
            if sentences and pause_match:
                sentences[-1]["text"] += f" [停顿{pause_match.group(1)}秒]"
            continue

        # 处理[强调]标记
        s = s.replace('[强调]', '')

        sentences.append({
            "text": s,
            "startTime": 0,  # TTS后填充
            "endTime": 0
        })

    return sentences


# ==================== 主生成流程 ====================
def generate_scripts(books: List[Dict], api: str = "minimax", dry_run: bool = False) -> List[Dict]:
    """
    为书籍列表生成字幕文稿

    Args:
        books: 书籍数据列表
        api: API类型 (minimax/doubao)
        dry_run: 预览模式，不实际调用API

    Returns:
        List[Dict]: 更新后的书籍数据（含script/quotes/sentences字段）
    """
    # 确保输出目录
    SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)

    # 初始化API客户端
    generator = None
    if not dry_run:
        if api == "minimax":
            api_key = os.getenv("ANTHROPIC_API_KEY", "")
            base_url = os.getenv("ANTHROPIC_BASE_URL", "https://api.minimaxi.com/anthropic")
            if api_key:
                generator = MiniMaxScriptGenerator(api_key, base_url)
            else:
                logger.error("❌ 未配置 ANTHROPIC_API_KEY，无法使用 MiniMax API")
                logger.info("💡 请在 pipeline/.env 中设置: ANTHROPIC_API_KEY=你的密钥")
        elif api == "doubao":
            api_key = os.getenv("DOUBAO_API_KEY", "")
            base_url = os.getenv("DOUBAO_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
            model = os.getenv("DOUBAO_MODEL", "doubao-pro-32k")
            if api_key:
                generator = DoubaoScriptGenerator(api_key, base_url, model)
            else:
                logger.error("❌ 未配置 DOUBAO_API_KEY，无法使用豆包 API")

    if not generator and not dry_run:
        logger.warning("⚠️ 无可用API客户端，将使用模拟文稿")
        dry_run = True

    total = len(books)
    results = []

    logger.info(f"\n{'='*55}")
    logger.info(f"📝 开始生成字幕文稿 | API: {api if not dry_run else '模拟'}")
    logger.info(f"📊 共 {total} 本书待处理")
    logger.info(f"{'='*55}")

    for i, book in enumerate(books):
        title = book.get("title", "未知")
        author = book.get("author", "未知")
        description = book.get("description", "")

        # 检查是否已有文稿
        if book.get("script") and book.get("isGenerated"):
            logger.info(f"[{i+1}/{total}] ⏭️ 已有文稿，跳过: 《{title}》")
            results.append(book)
            continue

        logger.info(f"\n[{i+1}/{total}] 📖 生成: 《{title}》 - {author}")

        try:
            if dry_run:
                # 模拟文稿
                script, quotes_text = _generate_mock_script(title, author)
                quotes = _extract_quotes_from_text(quotes_text)
                char_count = len(re.findall(r'[\u4e00-\u9fa5]', script))
                source = "mock"
            else:
                # 真实API调用
                result = generator.generate(title, author, description)
                script = result["script"]
                quotes = result["quotes"]
                quotes_text = result.get("quotesText", "")
                char_count = result["charCount"]
                source = result["scriptSource"]

            # 分句
            sentences = split_sentences(script)

            # 保存单独的文稿文件
            script_file = SCRIPTS_DIR / f"{title}_script.txt"
            with open(script_file, 'w', encoding='utf-8') as f:
                f.write(script)

            quotes_file = SCRIPTS_DIR / f"{title}_quotes.txt"
            with open(quotes_file, 'w', encoding='utf-8') as f:
                f.write(quotes_text)

            # 更新书籍数据
            now = int(time.time() * 1000)
            book["script"] = script
            book["quotes"] = quotes_text
            book["scriptLength"] = char_count
            book["scriptSource"] = source
            book["scriptVersion"] = book.get("scriptVersion", 0) + 1
            book["sentences"] = sentences
            book["isGenerated"] = True
            book["updateTime"] = now

            results.append(book)
            logger.info(f"  ✅ 文稿生成完成: {char_count}字, {len(sentences)}句")
            logger.info(f"  💾 文稿: {script_file}")
            logger.info(f"  💾 金句: {quotes_file}")

        except Exception as e:
            logger.error(f"  ❌ 生成失败: {e}")
            book["script"] = book.get("script", "")
            book["scriptSource"] = "failed"
            book["isGenerated"] = False
            results.append(book)

        # API调用间隔
        if not dry_run and i < total - 1:
            delay = 3
            logger.info(f"  ⏳ 等待{delay}秒...")
            time.sleep(delay)

    # 汇总
    success = sum(1 for b in results if b.get("isGenerated"))
    failed = sum(1 for b in results if not b.get("isGenerated"))

    logger.info(f"\n{'='*55}")
    logger.info(f"📊 字幕生成汇总")
    logger.info(f"{'='*55}")
    logger.info(f"✅ 成功: {success} 本")
    logger.info(f"❌ 失败: {failed} 本")

    return results


def _generate_mock_script(title: str, author: str) -> tuple:
    """生成模拟文稿（测试/预览用）"""
    script = f"""各位听众朋友好，欢迎收听今天的读书分享节目。

[停顿1秒]

我是你们的老朋友，今天要为大家分享的是{author}的经典作品《{title}》。

[停顿1秒]

说到这本书啊，可能很多朋友都读过，也有很多朋友可能只是听说过名字。

[停顿1秒]

这本书自出版以来，深受广大读者喜爱，被翻译成多种语言，在全球范围内产生了深远影响。

[强调]《{title}》不仅仅是一本普通的书，它更是一面镜子，映照出我们内心深处最真实的渴望与追求。

[停顿1秒]

好了，今天的分享就到这里，感谢各位的聆听。

[停顿1秒]

希望这本书能给你带来一些思考和启发。

再见！"""

    quotes_text = f'"每一本好书，都是一次灵魂的对话。" —— 《{title}》\n"阅读是思考的起点，思考是智慧的源泉。" —— 《{title}》\n"在书中找到自己，在自己中找到世界。" —— 《{title}》'

    return script, quotes_text


def _extract_quotes_from_text(quotes_text: str) -> List[Dict]:
    """从金句文本中提取结构化金句"""
    quotes = []
    for line in quotes_text.split('\n'):
        line = line.strip()
        q_match = re.match(r'["""](.+?)["""]\s*(?:——|—)\s*(.+)', line)
        if q_match:
            quotes.append({"content": q_match.group(1), "source": q_match.group(2)})
    return quotes


# ==================== 入口 ====================
def load_env():
    """加载环境变量"""
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        with open(env_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ.setdefault(key.strip(), value.strip())

    # 也尝试从 miniprogram/.env 加载
    mp_env = Path(__file__).parent.parent / "miniprogram" / ".env"
    if mp_env.exists():
        with open(mp_env, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ.setdefault(key.strip(), value.strip())


def main():
    parser = argparse.ArgumentParser(description="字幕文稿生成工具")
    parser.add_argument("--input", type=str, help="输入JSON文件路径")
    parser.add_argument("--books", type=str, help="指定书名，逗号分隔")
    parser.add_argument("--api", choices=["minimax", "doubao"], default="minimax", help="API类型")
    parser.add_argument("--output", type=str, help="输出JSON文件路径")
    parser.add_argument("--dry-run", action="store_true", help="预览模式（使用模拟文稿）")
    args = parser.parse_args()

    # 加载环境变量
    load_env()

    # 加载书籍数据
    books = []
    if args.input:
        input_path = Path(args.input)
        if not input_path.is_absolute():
            input_path = DATA_DIR / args.input
        with open(input_path, 'r', encoding='utf-8') as f:
            books = json.load(f)
        logger.info(f"📂 加载数据: {input_path} ({len(books)} 本书)")
    elif args.books:
        book_names = [b.strip() for b in args.books.split(",")]
        books = [{"title": name, "author": "未知", "description": ""} for name in book_names]
    else:
        # 默认查找爬取输出
        default_input = DATA_DIR / "crawled_output.json"
        if default_input.exists():
            with open(default_input, 'r', encoding='utf-8') as f:
                books = json.load(f)
            logger.info(f"📂 使用默认数据: {default_input} ({len(books)} 本书)")
        else:
            logger.error("❌ 未指定输入文件，且无默认数据")
            sys.exit(1)

    # 生成文稿
    results = generate_scripts(books, api=args.api, dry_run=args.dry_run)

    # 保存结果
    output_path = Path(args.output) if args.output else DATA_DIR / "step2_books_with_script.json"
    if not output_path.is_absolute():
        output_path = DATA_DIR / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    logger.info(f"\n💾 结果已保存: {output_path}")
    logger.info(f"💡 下一步: python import_to_cloud.py --input {output_path.name}")


if __name__ == "__main__":
    main()
