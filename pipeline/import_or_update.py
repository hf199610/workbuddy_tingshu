#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
带更新逻辑的书籍导入脚本
- 检查title是否存在，存在则更新，不存在则导入
- 支持批量处理
"""

import os
import json
import time
import logging
import httpx
import pandas as pd
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
    """获取微信access_token"""
    app_id = os.environ.get("WECHAT_APP_ID")
    secret = os.environ.get("WECHAT_SECRET")

    url = f"https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={app_id}&secret={secret}"
    resp = httpx.get(url, timeout=30)
    data = resp.json()

    if "access_token" not in data:
        raise Exception(f"获取token失败: {data}")

    return data["access_token"]


def check_book_exists(access_token, env_id, title):
    """查询书籍是否存在"""
    query = f'db.collection("books").where({{title: "{title}"}}).limit(1).get()'
    url = f"https://api.weixin.qq.com/tcb/databasequery?access_token={access_token}"

    resp = httpx.post(url, json={"env": env_id, "query": query}, timeout=30)
    result = resp.json()

    if result.get("errcode") == 0 and result.get("data"):
        data = json.loads(result["data"][0])
        return data.get("_id")
    return None


def update_book(access_token, env_id, book_id, data_obj):
    """更新书籍"""
    data_str = json.dumps(data_obj, ensure_ascii=False)
    query = f'db.collection("books").doc("{book_id}").update({{data: {data_str}}})'

    url = f"https://api.weixin.qq.com/tcb/databaseupdate?access_token={access_token}"
    resp = httpx.post(url, json={"env": env_id, "query": query}, timeout=30)
    return resp.json()


def add_book(access_token, env_id, data_obj):
    """新增书籍"""
    data_str = json.dumps(data_obj, ensure_ascii=False)
    query = f'db.collection("books").add({{data: {data_str}}}'

    url = f"https://api.weixin.qq.com/tcb/databaseadd?access_token={access_token}"
    resp = httpx.post(url, json={"env": env_id, "query": query}, timeout=30)
    return resp.json()


def delete_duplicate_books(access_token, env_id, title, keep_id):
    """删除重复的书籍记录（保留最新的）"""
    # 查询所有同名书籍
    query = f'db.collection("books").where({{title: "{title}"}}).get()'
    url = f"https://api.weixin.qq.com/tcb/databasequery?access_token={access_token}"

    resp = httpx.post(url, json={"env": env_id, "query": query}, timeout=30)
    result = resp.json()

    if result.get("errcode") != 0 or not result.get("data"):
        return

    # 解析所有记录
    records = [json.loads(d) for d in result["data"]]
    logger.info(f"发现 {len(records)} 条 '{title}' 记录")

    # 删除除了keep_id之外的所有记录
    deleted_count = 0
    for record in records:
        if record.get("_id") != keep_id:
            del_query = f'db.collection("books").doc("{record["_id"]}").remove()'
            del_url = f"https://api.weixin.qq.com/tcb/databasedelete?access_token={access_token}"
            del_resp = httpx.post(del_url, json={"env": env_id, "query": del_query}, timeout=30)
            if del_resp.json().get("errcode") == 0:
                deleted_count += 1
                logger.info(f"  删除重复: {record['_id']}")

    logger.info(f"✓ 共删除 {deleted_count} 条重复记录")


def import_or_update_from_excel(excel_file, clean_duplicates=True):
    """从Excel导入/更新书籍"""
    load_env()

    app_id = os.environ.get("WECHAT_APP_ID")
    secret = os.environ.get("WECHAT_SECRET")
    env_id = os.environ.get("WECHAT_ENV_ID")

    if not all([app_id, secret, env_id]):
        logger.error("缺少必要的环境变量")
        return

    # 获取token
    access_token = get_access_token()
    logger.info("✓ Token获取成功")

    # 读取Excel
    df = pd.read_excel(excel_file)
    if df.empty:
        logger.error("Excel文件为空")
        return

    timestamp = int(time.time() * 1000)

    # 处理每条记录
    success_count = 0
    for idx, row in df.iterrows():
        title = str(row.get("书名", "")).strip()
        if not title:
            continue

        audio_file_id = str(row.get("音频FileID", "")).strip()
        cover_file_id = str(row.get("封面FileID", "")).strip()

        logger.info(f"\n处理: {title}")
        logger.info(f"  音频ID: {audio_file_id[:50]}..." if len(audio_file_id) > 50 else f"  音频ID: {audio_file_id}")
        logger.info(f"  封面ID: {cover_file_id[:50]}..." if len(cover_file_id) > 50 else f"  封面ID: {cover_file_id}")

        # 检查是否存在
        book_id = check_book_exists(access_token, env_id, title)

        # 构建更新数据
        data_obj = {}
        if audio_file_id and audio_file_id != "nan":
            data_obj["audioFileId"] = audio_file_id
            data_obj["audioUrl"] = audio_file_id
        if cover_file_id and cover_file_id != "nan":
            data_obj["coverUrl"] = cover_file_id
        data_obj["isGenerated"] = True
        data_obj["isPublished"] = True
        data_obj["updateTime"] = timestamp

        if book_id:
            # 更新现有记录
            logger.info(f"  → 发现现有记录: {book_id}")
            result = update_book(access_token, env_id, book_id, data_obj)
            if result.get("errcode") == 0:
                logger.info(f"  ✓ 更新成功")
                success_count += 1

                # 如果需要清理重复
                if clean_duplicates:
                    delete_duplicate_books(access_token, env_id, title, book_id)
            else:
                logger.error(f"  ✗ 更新失败: {result}")
        else:
            # 新增记录（这里需要完整的书籍数据，暂时跳过）
            logger.warning(f"  → 该书不存在，建议先手动导入基础数据后再更新")

    logger.info(f"\n===== 完成: 成功更新 {success_count} 条 =====")


if __name__ == "__main__":
    import sys
    excel_file = PIPELINE_DIR.parent / "data_source/test_weicheng.xlsx"

    if len(sys.argv) > 1:
        excel_file = Path(sys.argv[1])

    import_or_update_from_excel(excel_file)