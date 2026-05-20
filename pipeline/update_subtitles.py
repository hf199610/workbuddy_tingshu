#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
为书籍重新生成带时间戳的字幕
解决现有sentences时间戳全为0的问题
"""

import os
import sys
import json
import asyncio
import argparse
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from edge_tts_generator import EdgeTTSGenerator


def update_book_with_timestamps(book_json_file, output_file=None):
    """为书籍数据生成带时间戳的字幕"""
    with open(book_json_file, 'r', encoding='utf-8') as f:
        books = json.load(f)

    # 只处理这三本书（测试用）
    target_books = ['小王子', '活着', '三体']
    results = []
    gen = EdgeTTSGenerator()

    for book in books:
        title = book.get('title', '')

        # 跳过不在目标中的书
        if title not in target_books:
            results.append(book)
            print(f"⏭️ 跳过: {title}")
            continue

        script = book.get('script', '')

        if not script:
            print(f"⚠️ 跳过 {title}: 无脚本内容")
            results.append(book)
            continue

        print(f"\n🎵 处理: {title}")

        # 生成音频+字幕
        result = gen.generate(
            text=script,
            output_mp3=f"pipeline/output/audios/{title}.mp3",
            output_vtt=f"pipeline/output/audios/{title}.vtt",
            voice="zh-CN-YunxiNeural",
            rate="-5%",
            pitch="-2Hz"
        )

        # 转换字幕格式：时间戳从纳秒转为秒
        subtitles = []
        for sub in result['subtitles']:
            subtitles.append({
                "startTime": round(sub['start'] / 1000, 2),  # 毫秒转秒
                "endTime": round(sub['end'] / 1000, 2),
                "text": sub['text']
            })

        # 更新书籍数据
        book['sentences'] = subtitles
        # 正确格式化 HH:MM:SS
        hours = int(result['duration_seconds'] // 3600)
        minutes = int((result['duration_seconds'] % 3600) // 60)
        seconds = int(result['duration_seconds'] % 60)
        book['audioDurationText'] = f"{hours}:{minutes:02d}:{seconds:02d}"
        book['audioUrl'] = f"cloud://audio/{title}.mp3"

        print(f"  ✅ {len(subtitles)} 句字幕, 时长 {result['duration_seconds']:.1f}秒")

        results.append(book)

    # 保存结果
    if not output_file:
        output_file = book_json_file.replace('.json', '_with_timestamps.json')

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 已保存到: {output_file}")
    return results


def main():
    parser = argparse.ArgumentParser(description='为书籍生成带时间戳的字幕')
    parser.add_argument('input', help='书籍JSON文件')
    parser.add_argument('-o', '--output', help='输出文件')

    args = parser.parse_args()

    update_book_with_timestamps(args.input, args.output)


if __name__ == "__main__":
    main()