#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
从Excel更新围城的文件ID到云数据库
"""

import os
import json
import datetime
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


def update_weicheng():
    load_env()

    app_id = os.environ.get("WECHAT_APP_ID")
    secret = os.environ.get("WECHAT_SECRET")
    env_id = os.environ.get("WECHAT_ENV_ID")

    # 1. 获取token
    token_url = f"https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={app_id}&secret={secret}"
    resp = httpx.get(token_url, timeout=30)
    token_data = resp.json()
    if "access_token" not in token_data:
        logger.error(f"获取token失败: {token_data}")
        return

    access_token = token_data["access_token"]
    logger.info("✓ Token获取成功")

    # 2. 从Excel读取file ID
    excel_file = PIPELINE_DIR.parent / "data_source/test_weicheng.xlsx"
    import pandas as pd
    df = pd.read_excel(excel_file)
    row = df.iloc[0]

    book_title = row["书名"]
    audio_file_id = row["音频FileID"]
    cover_file_id = row["封面FileID"]

    logger.info(f"书名: {book_title}")
    logger.info(f"音频ID: {audio_file_id}")
    logger.info(f"封面ID: {cover_file_id}")

    # 3. 更新数据库
    import time
    update_timestamp = int(time.time() * 1000)

    # 使用标准JSON格式构建查询
    data_obj = {
        "audioFileId": audio_file_id,
        "coverUrl": cover_file_id,
        "isGenerated": True,
        "isPublished": True,
        "updateTime": update_timestamp
    }

    data_str = json.dumps(data_obj, ensure_ascii=False)
    query = f'db.collection("books").where({{title: "{book_title}"}}).update({{data: {data_str}}})'

    logger.info(f"更新Query: {query}")

    update_url = f"https://api.weixin.qq.com/tcb/databaseupdate?access_token={access_token}"
    body = {"env": env_id, "query": query}

    update_resp = httpx.post(update_url, json=body, timeout=30)
    result = update_resp.json()

    logger.info(f"更新结果: {result}")

    if result.get("errcode") == 0:
        logger.info("✅ 围城记录更新成功!")
    else:
        logger.error(f"❌ 更新失败: {result}")


if __name__ == "__main__":
    update_weicheng()