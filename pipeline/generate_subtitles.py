#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
为已有音频生成字幕时间戳
使用edge-tts从音频文件生成同步的字幕
"""

import os
import sys
import json
import asyncio
import argparse

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from edge_tts import SubMaker


async def generate_subtitles_from_audio(audio_file, output_file=None):
    """从音频文件生成字幕"""
    if not os.path.exists(audio_file):
        raise FileNotFoundError(f"音频文件不存在: {audio_file}")

    print(f"🎵 解析音频: {audio_file}")

    # 使用SubMaker解析音频时间戳
    sm = SubMaker()
    with open(audio_file, 'rb') as f:
        sm.load(f)

    # 获取字幕数据
    subtitles = sm.get_subtitles()

    print(f"📝 生成 {len(subtitles)} 个字幕片段")

    # 生成JSON格式
    result = []
    for i, sub in enumerate(subtitles):
        result.append({
            "index": i,
            "start": sub.get("offset") or 0,
            "end": sub.get("offset") + sub.get("duration") or 0,
            "text": sub.get("text", "")
        })

    # 如果没有output_file，默认输出到同名.json
    if not output_file:
        output_file = audio_file.replace('.mp3', '_subtitles.json')

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"✅ 已保存到: {output_file}")
    return result


def main():
    parser = argparse.ArgumentParser(description='从音频生成字幕时间戳')
    parser.add_argument('audio_file', help='音频文件路径')
    parser.add_argument('-o', '--output', help='输出文件路径')

    args = parser.parse_args()

    asyncio.run(generate_subtitles_from_audio(args.audio_file, args.output))


if __name__ == "__main__":
    main()