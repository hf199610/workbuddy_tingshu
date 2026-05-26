#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据库导入脚本
将书籍数据批量导入云数据库
"""

import json
import os
import sys

DATA_FILE = os.path.join(os.path.dirname(__file__), "..", "data_source", "books_with_audio_url.json")
QUOTES_FILE = os.path.join(os.path.dirname(__file__), "..", "data_source", "quotes_for_database_import.json")


def load_books():
    """加载书籍数据"""
    if not os.path.exists(DATA_FILE):
        print(f"❌ 文件不存在: {DATA_FILE}")
        return []

    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        books = json.load(f)

    print(f"📚 加载了 {len(books)} 本书")
    return books


def load_quotes():
    """加载金句数据"""
    if not os.path.exists(QUOTES_FILE):
        print(f"❌ 文件不存在: {QUOTES_FILE}")
        return []

    with open(QUOTES_FILE, 'r', encoding='utf-8') as f:
        quotes = json.load(f)

    print(f"💬 加载了 {len(quotes)} 条金句")
    return quotes


def generate_import_data():
    """生成可直接导入的数据"""
    books = load_books()
    quotes = load_quotes()

    # 统计
    books_with_audio = sum(1 for b in books if b.get('audioUrl'))
    quotes_with_audio = sum(1 for q in quotes if q.get('audioUrl'))

    print(f"\n📊 统计:")
    print(f"  - 总书籍: {len(books)}")
    print(f"  - 有音频: {books_with_audio}")
    print(f"  - 总金句: {len(quotes)}")
    print(f"  - 有音频: {quotes_with_audio}")

    # 输出导入 JSON
    output = {
        "books": books,
        "quotes": quotes,
        "import_options": {
            "books_collection": "books",
            "quotes_collection": "quotes",
            "books_fields": ["title", "author", "category", "description", "coverColor", "coverUrl", "audioUrl"],
            "quotes_fields": ["bookId", "text", "author", "audioUrl"]
        }
    }

    print(f"\n✅ 数据准备完成，可以导入云数据库")

    return output


if __name__ == "__main__":
    generate_import_data()