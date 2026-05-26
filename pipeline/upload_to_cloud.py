#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
云存储上传脚本
将音频文件上传到微信云存储，并生成带 URL 的数据库数据

使用方式：
1. 先用微信开发者工具上传一个占位文件，获取 cloudID 格式
2. 或者使用云 API 上传（需要AppID和secret）

简化版本：生成带本地路径的数据，供后续替换
"""

import os
import json

# 配置
AUDIO_DIR = os.path.join(os.path.dirname(__file__), "output", "audios")
DATA_FILE = os.path.join(os.path.dirname(__file__), "..", "data_source", "step4_for_database_import.json")
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "..", "data_source", "books_with_audio_url.json")

# 云存储路径前缀（需要在小程序中替换为真实 URL）
CLOUD_PATH_PREFIX = "cloud://audio/"


def list_audio_files():
    """列出所有 mp3 文件"""
    files = []
    for f in os.listdir(AUDIO_DIR):
        if f.endswith('.mp3'):
            files.append(f)
    return files


def main():
    # 加载原始数据
    print(f"📂 加载数据: {DATA_FILE}")
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        books = json.load(f)

    # 列出音频文件
    audio_files = list_audio_files()
    print(f"🎵 找到 {len(audio_files)} 个音频文件: {audio_files}")

    # 为每本书添加 audioUrl
    results = []
    for book in books:
        title = book.get("title", "")
        # 匹配音频文件
        matched_audio = None
        for audio_file in audio_files:
            audio_name = audio_file.replace('.mp3', '')
            if audio_name in title or title in audio_name:
                matched_audio = audio_file
                break

        # 添加云存储路径
        if matched_audio:
            cloud_path = CLOUD_PATH_PREFIX + matched_audio.replace('.mp3', '.mp3')
            book['audioUrl'] = cloud_path  # 暂时存云存储路径，小程序会转换为 URL
            book['audioFileName'] = matched_audio
            print(f"  ✅ {title}: {matched_audio}")
        else:
            book['audioUrl'] = ""
            book['audioFileName'] = ""
            print(f"  ⚠️  {title}: 无音频")

        results.append(book)

    # 保存结果
    print(f"\n💾 保存到: {OUTPUT_FILE}")
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # 统计
    total = len(results)
    with_audio = sum(1 for b in results if b.get('audioUrl'))
    print(f"\n📊 统计: {with_audio}/{total} 本书有音频")

    return results


if __name__ == "__main__":
    main()