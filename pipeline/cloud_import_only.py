#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
云数据库导入脚本（直接 HTTP API 方式，无需部署云函数）
直接读取已生成的 JSON 数据文件，通过微信云开发 HTTP API 导入

使用方法:
  python cloud_import_only.py           # 导入 books + quotes
  python cloud_import_only.py --books-only  # 只导入 books
  python cloud_import_only.py --quotes-only # 只导入 quotes
  python cloud_import_only.py --check       # 只检查，不导入
"""

import os
import sys
import json
import time
import logging
from pathlib import Path

# 路径配置
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data_source"
PIPELINE_DIR = Path(__file__).parent

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)


def load_env():
    """加载环境变量"""
    for env_path in [PIPELINE_DIR / ".env", BASE_DIR / ".env"]:
        if env_path.exists():
            with open(env_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        value = value.strip()
                        if value.startswith('${') and value.endswith('}'):
                            ref_key = value[2:-1]
                            value = os.getenv(ref_key, "")
                        os.environ.setdefault(key.strip(), value)


def get_access_token(app_id: str, secret: str) -> str:
    """获取微信 access_token"""
    import httpx

    url = "https://api.weixin.qq.com/cgi-bin/token"
    params = {
        "grant_type": "client_credential",
        "appid": app_id,
        "secret": secret
    }

    with httpx.Client(timeout=30.0) as client:
        response = client.get(url, params=params)
        result = response.json()

        if "access_token" in result:
            logger.info("✅ access_token 获取成功")
            return result["access_token"]
        else:
            raise RuntimeError(
                f"获取 access_token 失败: errcode={result.get('errcode')}, "
                f"errmsg={result.get('errmsg')}"
            )


def query_database(access_token: str, env_id: str, query: str) -> dict:
    """查询云数据库"""
    import httpx

    url = "https://api.weixin.qq.com/tcb/databasequery"
    params = {"access_token": access_token}

    data = {
        "env": env_id,
        "query": query
    }

    with httpx.Client(timeout=30.0) as client:
        response = client.post(url, params=params, json=data)
        return response.json()


def add_record(access_token: str, env_id: str, collection: str, record: dict) -> dict:
    """
    向云数据库添加单条记录
    使用 databaseadd 接口
    """
    import httpx

    url = "https://api.weixin.qq.com/tcb/databaseadd"
    params = {"access_token": access_token}

    # 将记录转为 JSON 字符串嵌入查询语句
    # 注意：微信API要求 query 是一个字符串
    record_json = json.dumps(record, ensure_ascii=False)

    query = f"db.collection('{collection}').add({{data: {record_json}}})"

    data = {
        "env": env_id,
        "query": query
    }

    with httpx.Client(timeout=30.0) as client:
        response = client.post(url, params=params, json=data)
        return response.json()


def check_collections(access_token: str, env_id: str) -> dict:
    """检查 books 和 quotes 集合是否存在及数据量"""
    results = {}

    for coll in ["books", "quotes"]:
        query = f"db.collection('{coll}').limit(1).get()"
        result = query_database(access_token, env_id, query)

        errcode = result.get("errcode", -1)
        if errcode == 0:
            count_query = f"db.collection('{coll}').count()"
            count_result = query_database(access_token, env_id, count_query)
            total = count_result.get("pager", {}).get("Total", "?")
            results[coll] = {"exists": True, "count": total}
        else:
            results[coll] = {"exists": False, "error": result.get("errmsg", "未知错误")}

    return results


def check_book_exists(access_token: str, env_id: str, title: str) -> bool:
    """检查书籍是否已存在"""
    # 转义单引号
    safe_title = title.replace("'", "\\'")
    query = f"db.collection('books').where({{title: '{safe_title}'}}).limit(1).get()"
    result = query_database(access_token, env_id, query)

    if result.get("errcode") == 0:
        data = result.get("data", [])
        return len(data) > 0
    return False


def import_books(access_token: str, env_id: str, books: list) -> dict:
    """逐条导入 books 数据"""
    total = len(books)
    imported = 0
    skipped = 0
    failed = 0
    errors = []

    for i, book in enumerate(books):
        title = book.get("title", f"未知_{i}")

        # 去重检查
        if check_book_exists(access_token, env_id, title):
            logger.info(f"  [{i+1}/{total}] ⏭️ 跳过已存在: 《{title}》")
            skipped += 1
            continue

        # 清理数据：移除不适合直接入库的大字段（sentences 太大会导致API失败）
        import_record = {k: v for k, v in book.items()}

        # 微信云开发单条记录大小限制为 512KB，但 query 字符串也有长度限制
        # 如果 sentences 很长，需要精简或拆分
        if "sentences" in import_record and len(import_record["sentences"]) > 200:
            logger.info(f"     ⚠️ sentences 过长({len(import_record['sentences'])}句)，截取前200句")
            import_record["sentences"] = import_record["sentences"][:200]

        logger.info(f"  [{i+1}/{total}] 📥 导入: 《{title}》...")

        result = add_record(access_token, env_id, "books", import_record)

        if result.get("errcode") == 0:
            inserted_ids = result.get("id_list", [])
            imported += 1
            logger.info(f"     ✅ 成功 (id: {inserted_ids[0] if inserted_ids else '?'})")
        else:
            failed += 1
            errmsg = result.get("errmsg", "未知错误")
            errcode = result.get("errcode", "?")
            logger.error(f"     ❌ 失败: errcode={errcode}, {errmsg}")
            errors.append({
                "title": title,
                "errcode": errcode,
                "errmsg": errmsg
            })

            # 如果是 query 太长的错误，尝试不包含 script 和 sentences
            if "query" in errmsg.lower() or "size" in errmsg.lower() or "limit" in errmsg.lower():
                logger.info(f"     🔄 尝试精简数据重试...")
                slim_record = {k: v for k, v in import_record.items()
                              if k not in ("sentences", "script")}
                slim_record["sentences"] = []  # 空数组占位
                slim_record["script"] = import_record.get("script", "")[:3000]  # 截取前3000字

                result2 = add_record(access_token, env_id, "books", slim_record)
                if result2.get("errcode") == 0:
                    imported += 1
                    failed -= 1
                    errors.pop()
                    logger.info(f"     ✅ 精简版导入成功")
                else:
                    logger.error(f"     ❌ 精简版也失败: {result2.get('errmsg', '')}")

        # 请求间隔，避免频率限制
        time.sleep(0.5)

    return {
        "success": True,
        "imported": imported,
        "skipped": skipped,
        "failed": failed,
        "errors": errors
    }


def import_quotes(access_token: str, env_id: str, quotes: list) -> dict:
    """逐条导入 quotes 数据"""
    total = len(quotes)
    imported = 0
    skipped = 0
    failed = 0
    errors = []

    for i, quote in enumerate(quotes):
        content = quote.get("content", "")
        book_name = quote.get("bookName", "")

        logger.info(f"  [{i+1}/{total}] 📥 导入金句: 《{book_name}》- {content[:20]}...")

        result = add_record(access_token, env_id, "quotes", quote)

        if result.get("errcode") == 0:
            inserted_ids = result.get("id_list", [])
            imported += 1
            if (i + 1) % 10 == 0:
                logger.info(f"     ✅ 进度: {i+1}/{total}")
        else:
            failed += 1
            errmsg = result.get("errmsg", "未知错误")
            errcode = result.get("errcode", "?")
            logger.error(f"     ❌ 失败: errcode={errcode}, {errmsg}")
            errors.append({
                "content": content[:30],
                "bookName": book_name,
                "errcode": errcode,
                "errmsg": errmsg
            })

        # 请求间隔
        time.sleep(0.3)

    return {
        "success": True,
        "imported": imported,
        "skipped": skipped,
        "failed": failed,
        "errors": errors
    }


def main():
    import argparse

    parser = argparse.ArgumentParser(description="听书小程序 - 云数据库导入工具（HTTP API 直接导入）")
    parser.add_argument("--books-only", action="store_true", help="只导入 books 集合")
    parser.add_argument("--quotes-only", action="store_true", help="只导入 quotes 集合")
    parser.add_argument("--check", action="store_true", help="只检查集合状态，不导入")
    parser.add_argument("--dry-run", action="store_true", help="模拟运行，不实际导入")
    args = parser.parse_args()

    # 加载环境变量
    load_env()

    app_id = os.getenv("WECHAT_APP_ID", "")
    secret = os.getenv("WECHAT_SECRET", "")
    env_id = os.getenv("WECHAT_ENV_ID", "cloud1-d2ggs9k1bf3aa2a18")

    if not app_id or not secret:
        logger.error("❌ 未配置 WECHAT_APP_ID 或 WECHAT_SECRET")
        logger.info("请在 pipeline/.env 中设置微信云开发参数")
        sys.exit(1)

    print(f"""
╔══════════════════════════════════════════════════════════╗
║                                                          ║
║     ☁️ 听书小程序 - 云数据库导入工具 v2.0                  ║
║     （直接 HTTP API，无需部署云函数）                       ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝

📋 AppID: {app_id}
☁️  环境ID: {env_id}
""")

    # 1. 获取 access_token
    logger.info("🔑 获取 access_token...")
    try:
        access_token = get_access_token(app_id, secret)
    except RuntimeError as e:
        logger.error(f"❌ {e}")
        logger.info("\n请检查 WECHAT_APP_ID 和 WECHAT_SECRET 是否正确")
        sys.exit(1)

    # 2. 检查集合状态
    logger.info("\n📊 检查云数据库集合状态...")
    coll_status = check_collections(access_token, env_id)
    for coll, status in coll_status.items():
        if status["exists"]:
            logger.info(f"  ✅ {coll}: {status['count']} 条记录")
        else:
            logger.warning(f"  ⚠️ {coll}: 不存在或无权限 - {status.get('error', '')}")
            logger.info(f"     请先在云开发控制台创建 {coll} 集合")

    if args.check:
        print("\n✅ 检查完成")
        return

    # 3. 加载数据文件
    books_file = DATA_DIR / "step4_for_database_import.json"
    quotes_file = DATA_DIR / "quotes_for_database_import.json"

    books = []
    quotes = []

    if not args.quotes_only:
        if not books_file.exists():
            logger.error(f"❌ 找不到 books 数据文件: {books_file}")
        else:
            with open(books_file, 'r', encoding='utf-8') as f:
                books = json.load(f)
            logger.info(f"📄 加载 books 数据: {len(books)} 本")

    if not args.books_only:
        if not quotes_file.exists():
            logger.error(f"❌ 找不到 quotes 数据文件: {quotes_file}")
        else:
            with open(quotes_file, 'r', encoding='utf-8') as f:
                quotes = json.load(f)
            logger.info(f"📄 加载 quotes 数据: {len(quotes)} 条")

    if not books and not quotes:
        logger.error("❌ 没有可导入的数据")
        sys.exit(1)

    if args.dry_run:
        logger.info("\n🧪 模拟运行模式，不实际导入")
        logger.info(f"  📚 将导入 {len(books)} 本 books")
        logger.info(f"  💬 将导入 {len(quotes)} 条 quotes")
        return

    # 4. 导入 books
    books_result = None
    if books and not args.quotes_only:
        print(f"\n{'═'*60}")
        print(f"📚 开始导入 books 集合（{len(books)} 本）...")
        print(f"{'═'*60}")

        books_result = import_books(access_token, env_id, books)

        logger.info(f"\n📚 Books 导入结果:")
        logger.info(f"   ✅ 成功: {books_result['imported']} 本")
        logger.info(f"   ⏭️  跳过: {books_result['skipped']} 本（已存在）")
        logger.info(f"   ❌ 失败: {books_result['failed']} 本")
        if books_result['errors']:
            for err in books_result['errors'][:5]:
                logger.warning(f"   ⚠️ {err}")

    # 5. 导入 quotes
    quotes_result = None
    if quotes and not args.books_only:
        print(f"\n{'═'*60}")
        print(f"💬 开始导入 quotes 集合（{len(quotes)} 条）...")
        print(f"{'═'*60}")

        quotes_result = import_quotes(access_token, env_id, quotes)

        logger.info(f"\n💬 Quotes 导入结果:")
        logger.info(f"   ✅ 成功: {quotes_result['imported']} 条")
        logger.info(f"   ⏭️  跳过: {quotes_result['skipped']} 条（已存在）")
        logger.info(f"   ❌ 失败: {quotes_result['failed']} 条")
        if quotes_result['errors']:
            for err in quotes_result['errors'][:5]:
                logger.warning(f"   ⚠️ {err}")

    # 6. 最终汇总
    print(f"\n{'═'*60}")
    print(f"🎉 导入完成！")
    print(f"{'═'*60}")

    if books_result:
        print(f"  📚 Books: {books_result['imported']} 成功 / {books_result['skipped']} 跳过 / {books_result['failed']} 失败")
    if quotes_result:
        print(f"  💬 Quotes: {quotes_result['imported']} 成功 / {quotes_result['skipped']} 跳过 / {quotes_result['failed']} 失败")

    # 7. 验证
    logger.info("\n📊 验证导入结果...")
    coll_status_after = check_collections(access_token, env_id)
    for coll, status in coll_status_after.items():
        if status["exists"]:
            logger.info(f"  📊 {coll}: {status['count']} 条记录")


if __name__ == "__main__":
    main()
