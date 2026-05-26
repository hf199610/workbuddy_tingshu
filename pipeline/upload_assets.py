#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
上传围城的音频和封面到云存储，然后更新数据库记录
"""

import os
import json
import logging
import httpx
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
    env_path = PIPELINE_DIR / ".env"
    if env_path.exists():
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ.setdefault(key.strip(), value.strip())


def get_access_token():
    """获取微信access_token"""
    app_id = os.getenv("WECHAT_APP_ID")
    secret = os.getenv("WECHAT_SECRET")
    url = f"https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={app_id}&secret={secret}"
    with httpx.Client(timeout=30.0) as client:
        resp = client.get(url)
        result = resp.json()
        if "access_token" in result:
            return result["access_token"]
        else:
            raise RuntimeError(f"获取token失败: {result}")


def upload_to_cloud(file_path: Path, path_type: str = "audio") -> str:
    """上传文件到云存储，返回file_id"""
    access_token = get_access_token()
    env_id = os.getenv("WECHAT_ENV_ID")

    # 获取上传URL
    url1 = f"https://api.weixin.qq.com/tcb/uploadfile?access_token={access_token}"
    data = {
        "env": env_id,
        "path": f"{path_type}/{file_path.name}",
        "expires": 3600
    }

    with httpx.Client(timeout=60.0) as client:
        # 获取上传签名
        resp = client.post(url1, json=data)
        result = resp.json()
        logger.info(f"上传响应: {result}")

        if result.get("errcode") != 0:
            return {"success": False, "error": result}

        upload_url = result["url"]
        token = result["token"]
        authorization = result["authorization"]
        cos_file_id = result["cos_file_id"]

        # 上传文件
        with open(file_path, 'rb') as f:
            file_data = f.read()

        files = {'file': (file_path.name, file_data)}
        data2 = {
            'key': f"{path_type}/{file_path.name}",
            'Signature': authorization,
            'x-cos-security-token': token,
            'x-cos-meta-fileid': cos_file_id,
        }

        resp2 = client.post(upload_url, files=files, data=data2)
        logger.info(f"上传状态: {resp2.status_code}")

        if resp2.status_code in [200, 201, 204]:
            file_id = f"cloud://{env_id}.{cos_file_id}"
            return {"success": True, "file_id": file_id}
        else:
            return {"success": False, "error": resp2.text}


def update_book_record(title: str, audio_url: str, cover_url: str, audio_duration: str) -> dict:
    """更新书籍记录"""
    access_token = get_access_token()
    env_id = os.getenv("WECHAT_ENV_ID")

    # 构建更新语句
    query = f'''db.collection("books").where({{title: "{title}"}}).update({{data: {{
        audioUrl: "{audio_url}",
        coverUrl: "{cover_url}",
        audioDurationText: "{audio_duration}",
        isGenerated: true,
        isPublished: true
    }}}})'''

    logger.info(f"更新查询: {query}")

    url = f"https://api.weixin.qq.com/tcb/databaseupdate?access_token={access_token}"
    data = {"env": env_id, "query": query}

    with httpx.Client(timeout=30.0) as client:
        resp = client.post(url, json=data)
        result = resp.json()
        if result.get("errcode") == 0:
            return {"success": True}
        else:
            logger.info(f"更新失败: {result}")
            # 可能记录不存在，尝试添加
            return add_new_record(title, audio_url, cover_url, audio_duration)


def add_new_record(title: str, audio_url: str, cover_url: str, audio_duration: str) -> dict:
    """添加新记录"""
    access_token = get_access_token()
    env_id = os.getenv("WECHAT_ENV_ID")

    query = f'''db.collection("books").add({{data: {{
        title: "{title}",
        author: "钱锺书",
        category: 1,
        categoryName: "经典名著",
        publisher: "人民文学出版社",
        description: "《围城》是中国现代文学史上一部风格独特的讽刺小说，被誉为新儒林外史",
        coverUrl: "{cover_url}",
        coverColor: "#E74C3C",
        audioUrl: "{audio_url}",
        audioDurationText: "{audio_duration}",
        isGenerated: true,
        isPublished: true,
        createTime: 1779261592000,
        updateTime: 1779261592000
    }}}})'''

    logger.info(f"添加查询: {query[:200]}...")

    url = f"https://api.weixin.qq.com/tcb/databaseadd?access_token={access_token}"
    data = {"env": env_id, "query": query}

    with httpx.Client(timeout=30.0) as client:
        resp = client.post(url, json=data)
        result = resp.json()
        return result


if __name__ == "__main__":
    load_env()

    cover_file = PIPELINE_DIR / "output/covers/围城.jpg"
    audio_file = PIPELINE_DIR / "output/audios/围城.mp3"

    print("=" * 40)
    print("1. 上传封面图片...")
    cover_result = upload_to_cloud(cover_file, "image")
    print(f"封面结果: {cover_result}")

    print("=" * 40)
    print("2. 上传音频文件...")
    audio_result = upload_to_cloud(audio_file, "audio")
    print(f"音频结果: {audio_result}")

    print("=" * 40)
    print("3. 更新数据库记录...")

    # 注意：这里应该填用户已更正的文件ID
    # 如果用户已经手动上传了，可以使用用户给的ID
    # 暂时使用刚才得到的ID
    cover_url = cover_result.get("file_id", "")
    audio_url = audio_result.get("file_id", "")

    # 更新记录
    update_result = update_book_record(
        "围城",
        audio_url,  # 用户已更正的文件ID应该替换这里
        cover_url,  # 用户已更正的文件ID应该替换这里
        "约15分钟"
    )
    print(f"更新结果: {update_result}")