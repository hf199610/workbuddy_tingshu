#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
批量下载豆瓣封面图片
用法: python download_covers.py
       python download_covers.py --book "书名"
"""

import os
import sys
import json
import logging
import httpx
from pathlib import Path
from typing import Optional, List

BASE_DIR = Path(__file__).parent.parent
OUTPUT_COVERS = BASE_DIR / "pipeline/output/covers"
OUTPUT_AUDIOS = BASE_DIR / "pipeline/output/audios"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)


def search_douban(book_name: str) -> Optional[str]:
    """搜索豆瓣书籍，返回封面URL"""
    try:
        url = f"https://book.douban.com/search?q={book_name}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://book.douban.com/",
        }

        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            resp = client.get(url, headers=headers)
            text = resp.text

            # 找到第一个匹配的封面图
            import re
            # 匹配 pattern: img src="https://img\d+.doubanio.com/view/subject/s/public/xxx.jpg"
            pattern = r'img src="(https://img\d+\.doubanio\.com/view/subject/s/public/[^"]+\.jpg)"'
            matches = re.findall(pattern, text)
            if matches:
                # 返回小图，换成大图
                small_url = matches[0]
                large_url = small_url.replace("/s/", "/l/")
                return large_url
    except Exception as e:
        logger.warning(f"搜索失败: {e}")
    return None


def download_cover(book_name: str, output_dir: Path = None) -> bool:
    """下载单本书的封面"""
    if output_dir is None:
        output_dir = OUTPUT_COVERS

    output_dir.mkdir(parents=True, exist_ok=True)

    # 搜索URL
    cover_url = search_douban(book_name)
    if not cover_url:
        logger.error(f"未找到封面: {book_name}")
        return False

    # 下载
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://book.douban.com/",
    }

    safe_name = "".join(c for c in book_name if c not in r'<>:"/\|?*')
    output_path = output_dir / f"{safe_name}.jpg"

    try:
        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            resp = client.get(cover_url, headers=headers)
            if resp.status_code == 200:
                with open(output_path, "wb") as f:
                    f.write(resp.content)
                logger.info(f"下载成功: {output_path} ({len(resp.content)} bytes)")
                return True
    except Exception as e:
        logger.error(f"下载失败: {e}")

    return False


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="下载豆瓣封面")
    parser.add_argument("--book", "-b", help="书名")
    args = parser.parse_args()

    if args.book:
        download_cover(args.book)
    else:
        # 从数据文件读取
        data_file = BASE_DIR / "data_source/books_with_audio_url.json"
        if data_file.exists():
            data = json.loads(data_file.read_text(encoding="utf-8"))
            for book in data[:5]:  # 前5本
                download_cover(book.get("title", ""))