#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
直接导入完整书籍数据到云数据库（包含讲解稿）
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
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
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


def escape_str(s):
    """转义字符串中的特殊字符"""
    # 先替换反斜杠，再替换引号，再替换换行
    s = str(s)
    s = s.replace("\\", "\\\\")  # 反斜杠
    s = s.replace('"', '\\"')     # 双引号
    s = s.replace("\n", " ")      # 换行符转空格
    s = s.replace("\r", " ")      # 回车符转空格
    s = s.replace("\t", " ")      # 制表符转空格
    return s


def add_book(access_token, env_id, data_obj):
    """新增书籍 - 使用正确的JSON转义"""
    # 构建query字符串
    parts = []
    for key, value in data_obj.items():
        if isinstance(value, str):
            s = escape_str(value)
            parts.append(f'{key}: "{s}"')
        elif isinstance(value, list):
            items = []
            for item in value:
                if isinstance(item, dict):
                    item_parts = []
                    for k, v in item.items():
                        if isinstance(v, str):
                            v = escape_str(v)
                        item_parts.append(f'{k}: "{v}"')
                    items.append("{" + ", ".join(item_parts) + "}")
                else:
                    items.append(str(item))
            parts.append(f'{key}: [{", ".join(items)}]')
        elif isinstance(value, dict):
            inner_parts = []
            for k, v in value.items():
                if isinstance(v, str):
                    v = escape_str(v)
                inner_parts.append(f'{k}: "{v}"')
            parts.append(f'{key}: {{{", ".join(inner_parts)}}}')
        else:
            parts.append(f'{key}: "{value}"')

    data_str = "{" + ", ".join(parts) + "}"
    query = f'db.collection("books").add({{data: {data_str}}})'

    url = f"https://api.weixin.qq.com/tcb/databaseadd?access_token={access_token}"
    resp = httpx.post(url, json={"env": env_id, "query": query}, timeout=60)
    result = resp.json()

    if result.get("errcode") == 0:
        book_id = result.get("id_list", [None])[0]
        logger.info(f"✓ 导入成功，ID: {book_id}")
        return book_id
    else:
        logger.error(f"✗ 导入失败: {result}")
        return None


def main():
    load_env()
    app_id = os.environ.get("WECHAT_APP_ID")
    secret = os.environ.get("WECHAT_SECRET")
    env_id = os.environ.get("WECHAT_ENV_ID")

    if not all([app_id, secret, env_id]):
        logger.error("缺少环境变量")
        return

    # 从Excel读取FileID
    excel_file = PIPELINE_DIR.parent / "pipeline/output/test_mockingbird.xlsx"
    df = pd.read_excel(excel_file)
    row = df.iloc[0]

    book_title = row["书名"]
    audio_file_id = row["音频FileID"]
    cover_file_id = row["封面FileID"]

    # 读取讲解稿
    script_file = PIPELINE_DIR.parent / f"pipeline/output/data/{book_title}_script.txt"
    if script_file.exists():
        with open(script_file, "r", encoding="utf-8") as f:
            script = f.read()
    else:
        script = "讲解稿待补充"
        logger.warning(f"讲解稿文件不存在: {script_file}")

    logger.info(f"书名: {book_title}")
    logger.info(f"音频ID: {audio_file_id[:50]}...")
    logger.info(f"封面ID: {cover_file_id[:50]}...")
    logger.info(f"讲解稿: {len(script)} 字")

    # 获取token
    access_token = get_access_token()
    logger.info("✓ Token获取成功")

    timestamp = int(time.time() * 1000)

    # 构建完整数据
    data_obj = {
        "title": book_title,
        "author": "哈珀·李",
        "category": "文学",
        "intro": """《杀死一只知更鸟》是美国女作家哈珀·李发表于1960年的长篇小说。
小说以大萧条时期的南方小镇为背景，通过白人律师阿蒂克斯为黑人司机辩护的故事，
揭示了美国南方种族歧视的黑暗现实。小说以童真的视角展现了正义与善良的力量，
成为美国文学的经典之作，1961年获得普利策小说奖。""",
        "script": script,
        "scriptLength": len(script),
        "quotes": [
            {"content": "你永远不能真正了解一个人，除非你站在他的角度考虑问题。", "author": "阿蒂克斯"},
            {"content": "杀死一只知更鸟是一种罪过，因为它们只是唱歌给人听，什么坏事也不做。", "author": "阿蒂克斯"},
            {"content": "勇敢就是明知会失败，仍然坚持下去。", "author": "阿蒂克斯"},
        ],
        "quotesCount": 3,
        "audioFileId": audio_file_id,
        "audioUrl": audio_file_id,
        "coverUrl": cover_file_id,
        "coverColor": "#4A90A4",
        "duration": "00:08:00",
        "isGenerated": True,
        "isPublished": True,
        "isHot": False,
        "createTime": timestamp,
        "updateTime": timestamp,
    }

    logger.info("\n开始导入数据库...")
    book_id = add_book(access_token, env_id, data_obj)

    if book_id:
        logger.info(f"\n===== 成功！书籍ID: {book_id} =====")
    else:
        logger.error("\n===== 导入失败 =====")


if __name__ == "__main__":
    main()