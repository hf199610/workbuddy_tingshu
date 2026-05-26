#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
批量生成音频脚本
为数据库中的书籍生成音频文件
"""

import json
import os
import sys
import asyncio
import logging

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from edge_tts_generator import EdgeTTSGenerator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DATA_FILE = os.path.join(os.path.dirname(__file__), "..", "data_source", "step4_for_database_import.json")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output", "audios")

# 限制生成数量
MAX_BOOKS = 10


async def generate_audio_for_book(book: dict, output_path: str) -> dict:
    """为单本书生成音频"""
    title = book.get("title", "unknown")
    script = book.get("script", "")

    if not script:
        logger.warning(f"⚠️  {title} 没有脚本，跳过")
        return None

    # 清理脚本中的 TTS 标记
    script = script.replace("[停顿1秒]", "")
    script = script.replace("[停顿2秒]", "")
    script = script.replace("[强调]", "")
    script = script.replace("[音乐]", "")
    script = script.replace("[音效]", "")
    script = script.replace("\n\n\n", "\n\n")
    script = script.strip()

    if len(script) < 50:
        logger.warning(f"⚠️  {title} 脚本太短，跳过")
        return None

    # 生成音频
    gen = EdgeTTSGenerator(voice="zh-CN-YunxiNeural")
    result = await gen.generate_async(
        text=script,
        output_mp3=output_path,
    )

    logger.info(f"✅ 生成完成: {title} ({result['duration_seconds']:.1f}秒)")
    return result


async def main():
    # 加载数据
    logger.info(f"📂 加载数据: {DATA_FILE}")
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        books = json.load(f)

    logger.info(f"📚 共有 {len(books)} 本书")

    # 限制数量
    books_to_process = books[:MAX_BOOKS]
    logger.info(f"🎯 将处理 {len(books_to_process)} 本书")

    # 确保输出目录存在
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 逐个生成
    results = []
    for i, book in enumerate(books_to_process):
        title = book.get("title", "unknown")
        output_path = os.path.join(OUTPUT_DIR, f"{title}.mp3")

        logger.info(f"\n[{i+1}/{len(books_to_process)}] 生成: {title}")
        logger.info(f"   脚本长度: {len(book.get('script', ''))} 字")

        try:
            result = await generate_audio_for_book(book, output_path)
            if result:
                results.append({
                    "title": title,
                    "audio_path": output_path,
                    "duration": result.get("duration_seconds", 0),
                    "size": result.get("mp3_size_bytes", 0),
                })
        except Exception as e:
            logger.error(f"❌ 生成失败: {title} - {e}")

    # 输出结果
    print(f"\n{'='*50}")
    print(f"📊 生成结果: {len(results)}/{len(books_to_process)} 成功")
    print(f"{'='*50}")
    for r in results:
        print(f"  📄 {r['title']}: {r['duration']:.1f}秒, {r['size']/1024:.1f}KB")

    return results


if __name__ == "__main__":
    asyncio.run(main())