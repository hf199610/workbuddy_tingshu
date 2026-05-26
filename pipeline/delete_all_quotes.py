#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
删除数据库中所有书籍的金句字段内容
使用前请谨慎确认！
"""

import os
import json
import logging
import httpx
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
PIPELINE_DIR = Path(__file__).parent

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def load_env():
    for env_path in [PIPELINE_DIR / ".env", BASE_DIR / ".env"]:
        if env_path.exists():
            with open(env_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        os.environ.setdefault(key.strip(), value.strip())


def get_access_token():
    app_id = os.environ.get("WECHAT_APP_ID")
    secret = os.environ.get("WECHAT_SECRET")
    url = f"https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={app_id}&secret={secret}"
    resp = httpx.get(url, timeout=30)
    data = resp.json()
    if "access_token" not in data:
        raise Exception(f"获取token失败: {data}")
    return data["access_token"]


def query_all_books(access_token, env_id, limit=100):
    """查询所有书籍"""
    all_books = []
    offset = 0

    while True:
        query = f'db.collection("books").limit({limit}).skip({offset}).get()'
        url = f"https://api.weixin.qq.com/tcb/databasequery?access_token={access_token}"

        resp = httpx.post(url, json={"env": env_id, "query": query}, timeout=30)
        result = resp.json()

        if result.get("errcode") != 0:
            logger.error(f"查询失败: {result}")
            break

        data = result.get("data", [])
        if not data:
            break

        for item in data:
            try:
                book = json.loads(item)
                all_books.append(book)
            except:
                pass

        if len(data) < limit:
            break

        offset += limit
        logger.info(f"  已获取 {len(all_books)} 条...")

    return all_books


def clear_quotes(access_token, env_id, book_id):
    """清空单本书籍的金句"""
    # 更新为空的quotes数组
    data_obj = {
        "quotes": [],
        "quotesCount": 0,
    }

    data_str = json.dumps(data_obj, ensure_ascii=False)
    query = f'db.collection("books").doc("{book_id}").update({{data: {data_str}}})'

    url = f"https://api.weixin.qq.com/tcb/databaseupdate?access_token={access_token}"
    resp = httpx.post(url, json={"env": env_id, "query": query}, timeout=30)
    return resp.json()


def main():
    import argparse
    parser = argparse.ArgumentParser(description='删除所有书籍的金句')
    parser.add_argument('--dry-run', action='store_true', help='仅预览不执行')
    args = parser.parse_args()

    load_env()

    app_id = os.environ.get("WECHAT_APP_ID")
    secret = os.environ.get("WECHAT_SECRET")
    env_id = os.environ.get("WECHAT_ENV_ID")

    if not all([app_id, secret, env_id]):
        logger.error("缺少必要的环境变量")
        return

    if not args.dry_run:
        confirm = input("⚠️ 即将删除所有书籍的金句！此操作不可逆！\n确认执行? (yes/no): ")
        if confirm.lower() != 'yes':
            logger.info("已取消")
            return

    access_token = get_access_token()
    logger.info("Token获取成功")

    logger.info("查询所有书籍...")
    books = query_all_books(access_token, env_id)
    logger.info(f"共找到 {len(books)} 本书")

    # 统计有金句的书籍
    books_with_quotes = [b for b in books if b.get('quotes') and len(b.get('quotes', [])) > 0]
    logger.info(f"其中 {len(books_with_quotes)} 本有金句")

    if args.dry_run:
        logger.info("=== DRY RUN 模式，仅预览 ===")
        for book in books_with_quotes[:10]:
            logger.info(f"  - {book.get('title', 'unknown')}: {len(book.get('quotes', []))} 条金句")
        if len(books_with_quotes) > 10:
            logger.info(f"  ... 还有 {len(books_with_quotes) - 10} 本")
        return

    # 执行删除
    success_count = 0
    fail_count = 0

    for i, book in enumerate(books_with_quotes):
        book_id = book.get('_id')
        title = book.get('title', 'unknown')
        quotes_count = len(book.get('quotes', []))

        logger.info(f"[{i+1}/{len(books_with_quotes)}] 处理: {title}")

        result = clear_quotes(access_token, env_id, book_id)
        if result.get('errcode') == 0:
            success_count += 1
            logger.info(f"  ✓ 已清空 {quotes_count} 条金句")
        else:
            fail_count += 1
            logger.error(f"  ✗ 失败: {result}")

    logger.info(f"\n{'='*50}")
    logger.info(f"金句删除完成!")
    logger.info(f"  成功: {success_count} 本")
    logger.info(f"  失败: {fail_count} 本")
    logger.info(f"{'='*50}")


if __name__ == "__main__":
    main()
