#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
简化版数据库导入脚本
修复了JSON转义问题，使用更安全的字符串处理
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


def escape_value(value):
    """安全转义任意值"""
    if value is None or value == "":
        return "null"
    elif isinstance(value, bool):
        return str(value).lower()
    elif isinstance(value, (int, float)):
        return str(value)
    elif isinstance(value, str):
        # 使用 repr 进行最安全的转义
        return repr(value)
    elif isinstance(value, list):
        items = [escape_value(item) for item in value]
        return "[" + ", ".join(items) + "]"
    else:
        return repr(str(value))


def import_single_book(book_data: dict) -> dict:
    """导入单本书籍到云数据库"""
    import httpx

    load_env()

    access_token = os.getenv("WECHAT_APP_ID") + ":" + os.getenv("WECHAT_SECRET")
    # 获取 access_token
    app_id = os.getenv("WECHAT_APP_ID")
    secret = os.getenv("WECHAT_SECRET")
    env_id = os.getenv("WECHAT_ENV_ID")

    # 获取token
    url = f"https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={app_id}&secret={secret}"
    with httpx.Client(timeout=30.0) as client:
        response = client.get(url)
        result = response.json()
        if "access_token" in result:
            access_token = result["access_token"]
        else:
            return {"success": False, "error": f"获取token失败: {result}"}

    # 构建格式化良好的文档字符串
    doc_lines = []
    for key, value in book_data.items():
        if isinstance(value, str):
            # 用三引号字符串更安全
            doc_lines.append(f'{key}: """{value}"""')
        elif isinstance(value, bool):
            doc_lines.append(f"{key}: {str(value).lower()}")
        elif isinstance(value, (int, float)):
            doc_lines.append(f"{key}: {value}")
        elif value is None:
            doc_lines.append(f"{key}: null")
        elif isinstance(value, list):
            items = []
            for item in value:
                if isinstance(item, str):
                    items.append(f'"""{item}"""')
                else:
                    items.append(str(item))
            doc_lines.append(f"{key}: [{', '.join(items)}]")
        else:
            doc_lines.append(f'{key}: """{str(value)}"""')

    query = 'db.collection("books").add({data: {' + ", ".join(doc_lines) + "}})"
    logger.info(f"Query: {query[:300]}...")

    # 执行添加
    url = f"https://api.weixin.qq.com/tcb/databaseadd?access_token={access_token}"
    data = {"env": env_id, "query": query}

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(url, json=data)
            result = response.json()
            if result.get("errcode") == 0:
                return {"success": True, "data": result}
            else:
                return {"success": False, "error": result}
    except Exception as e:
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    # 测试导入围城
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
    result = import_single_book(book)
    print(result)