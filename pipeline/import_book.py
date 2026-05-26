#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
云数据库导入脚本 - 使用标准JSON格式
"""

import os
import json
import logging
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
PIPELINE_DIR = Path(__file__).parent

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
                        os.environ.setdefault(key.strip(), value)


def build_doc_string(data: dict) -> str:
    """构建云数据库文档字符串 - 标准格式"""
    parts = []
    for key, value in data.items():
        if value is None:
            parts.append(f"{key}: null")
        elif isinstance(value, bool):
            parts.append(f"{key}: {str(value).lower()}")
        elif isinstance(value, (int, float)):
            parts.append(f"{key}: {value}")
        elif isinstance(value, str):
            # 用双引号，内部 \" 转义
            escaped = value.replace("\\", "\\\\").replace('"', '\\"')
            parts.append(f'{key}: "{escaped}"')
        elif isinstance(value, list):
            items = []
            for item in value:
                if isinstance(item, str):
                    e = item.replace("\\", "\\\\").replace('"', '\\"')
                    items.append(f'"{e}"')
                else:
                    items.append(str(item))
            parts.append(f"{key}: [{', '.join(items)}]")
        else:
            s = str(value).replace("\\", "\\\\").replace('"', '\\"')
            parts.append(f'{key}: "{s}"')
    return "{" + ", ".join(parts) + "}"


def import_book(book_data: dict) -> dict:
    """导入书籍"""
    import httpx

    load_env()

    app_id = os.getenv("WECHAT_APP_ID")
    secret = os.getenv("WECHAT_SECRET")
    env_id = os.getenv("WECHAT_ENV_ID")

    # 获取token
    url = f"https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={app_id}&secret={secret}"
    with httpx.Client(timeout=30.0) as client:
        r = client.get(url)
        token_result = r.json()
        if "access_token" in token_result:
            access_token = token_result["access_token"]
        else:
            return {"success": False, "error": token_result}

    # 构建查询
    data_str = build_doc_string(book_data)
    query = f'db.collection("books").add({{data: {data_str}}})'
    logger.info(f"Query: {query[:200]}...")

    # 添加记录
    url = f"https://api.weixin.qq.com/tcb/databaseadd?access_token={access_token}"
    body = {"env": env_id, "query": query}

    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(url, json=body)
            result = resp.json()
            if result.get("errcode") == 0:
                return {"success": True, "data": result}
            else:
                return {"success": False, "error": result, "query": query}
    except Exception as e:
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    # 导入围城
    book = {
        "title": "围城",
        "author": "钱锺书",
        "category": 1,
        "categoryName": "经典名著",
        "publisher": "人民文学出版社",
        "description": "《围城》是中国现代文学史上一部风格独特的讽刺小说，被誉为新儒林外史",
        "coverUrl": "https://img3.doubanio.com/lpic/s1070222.jpg",
        "coverColor": "#E74C3C",
        "isGenerated": True,
        "isPublished": True,
    }
    result = import_book(book)
    print(json.dumps(result, ensure_ascii=False, indent=2))