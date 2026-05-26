#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
生成单本书籍的完整流程 - 杀死一只知更鸟
"""

import os
import json
import time
import logging
import httpx
import pandas as pd
import base64
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
PIPELINE_DIR = Path(__file__).parent
OUTPUT_DIR = PIPELINE_DIR / "output"

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


# 书籍基础信息
BOOK_INFO = {
    "title": "杀死一只知更鸟",
    "author": "哈珀·李",
    "original_title": "To Kill a Mockingbird",
    "category": "文学",
    "douban_id": "12968320",
    "coverColor": "#4A90A4",  # 封面背景色
    "intro": """《杀死一只知更鸟》是美国女作家哈珀·李发表于1960年的长篇小说。
小说以大萧条时期的南方小镇为背景，通过白人律师阿蒂克斯为黑人司机辩护的故事，
揭示了美国南方种族歧视的黑暗现实。小说以童真的视角展现了正义与善良的力量，
成为美国文学的经典之作，1961年获得普利策小说奖。""",
    "quotes": [
        {"content": "你永远不能真正了解一个人，除非你站在他的角度考虑问题。", "author": "阿蒂克斯"},
        {"content": "杀死一只知更鸟是一种罪过，因为它们只是唱歌给人听，什么坏事也不做。", "author": "阿蒂克斯"},
        {"content": "勇敢就是明知会失败，仍然坚持下去。", "author": "阿蒂克斯"},
    ],
}


def get_access_token():
    app_id = os.environ.get("WECHAT_APP_ID")
    secret = os.environ.get("WECHAT_SECRET")
    url = f"https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={app_id}&secret={secret}"
    resp = httpx.get(url, timeout=30)
    data = resp.json()
    if "access_token" not in data:
        raise Exception(f"获取token失败: {data}")
    return data["access_token"]


def generate_script():
    from anthropic import Anthropic

    client = Anthropic(
        api_key=os.environ.get("ANTHROPIC_API_KEY"),
        base_url=os.environ.get("ANTHROPIC_BASE_URL", "https://api.minimaxi.com/anthropic"),
    )

    title = BOOK_INFO["title"]
    author = BOOK_INFO["author"]
    intro = BOOK_INFO["intro"]

    prompt = f"""请为《{title}》生成一段4200字左右的书籍讲解稿。

书籍信息：
- 作者：{author}
- 简介：{intro}

要求：
1. 详细生动地介绍这本书的写作背景、情节、人物、主题思想
2. 语言通俗易懂，适合听书场景
3. 控制在4000-4500字
4. 只输出讲解稿内容，不要其他说明"""

    try:
        msg = client.messages.create(
            model=os.environ.get("MINIMAX_MODEL", "MiniMax-M2.7"),
            max_tokens=8000,
            messages=[{"role": "user", "content": prompt}],
        )
        # 处理API返回的不同块类型
        for block in msg.content:
            if hasattr(block, 'text'):
                script = block.text.strip()
                break
            elif hasattr(block, 'type') and block.type == 'thinking':
                continue
        else:
            script = str(msg.content)
        logger.info(f"讲解稿生成成功 ({len(script)} 字)")
        return script
    except Exception as e:
        logger.error(f"生成讲解稿失败: {type(e)} - {e}")
        return None


def download_cover():
    """下载封面，失败时自动生成纯色文字封面"""
    douban_id = BOOK_INFO["douban_id"]
    urls_to_try = [
        f"https://img2.douban.com/view/material_raw/public/p{douban_id}.jpg",
        f"https://img9.douban.com/view/material_raw/public/p{douban_id}.jpg",
    ]

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    covers_dir = OUTPUT_DIR / "covers"
    covers_dir.mkdir(parents=True, exist_ok=True)
    cover_path = covers_dir / f"{BOOK_INFO['title']}.jpg"

    for cover_url in urls_to_try:
        try:
            logger.info(f"尝试下载封面: {cover_url}")
            resp = httpx.get(cover_url, timeout=30, follow_redirects=True)
            if resp.status_code == 200 and len(resp.content) > 5000:
                with open(cover_path, "wb") as f:
                    f.write(resp.content)
                logger.info(f"封面下载成功: {cover_path} ({len(resp.content)} bytes)")
                return cover_path
        except Exception as e:
            logger.warning(f"下载失败: {e}")
            continue

    # 下载失败，生成纯色文字封面
    logger.info("自动生成纯色文字封面...")
    return generate_text_cover(covers_dir)


def generate_text_cover(output_dir):
    """生成纯色+文字的简易封面"""
    try:
        from PIL import Image, ImageDraw, ImageFont

        title = BOOK_INFO["title"]
        author = BOOK_INFO["author"]
        color = BOOK_INFO.get("coverColor", "#4A90A4")

        img = Image.new("RGB", (400, 600), color=color)
        draw = ImageDraw.Draw(img)

        # 装饰边框
        draw.rectangle([20, 20, 380, 580], outline="white", width=3)

        # 字体
        try:
            font = ImageFont.truetype("C:/Windows/Fonts/simhei.ttf", 40)
        except:
            font = ImageFont.load_default()

        # 书名（居中，换行）
        chars_per_line = 6
        lines = [title[i:i+chars_per_line] for i in range(0, len(title), chars_per_line)]
        y = 250
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            text_width = bbox[2] - bbox[0]
            x = (400 - text_width) // 2
            draw.text((x, y), line, fill="white", font=font)
            y += 60

        # 作者名
        bbox = draw.textbbox((0, 0), author, font=font)
        author_width = bbox[2] - bbox[0]
        draw.text(((400 - author_width)//2, y + 20), author, fill="#FFFFFFCC", font=font)

        cover_path = output_dir / f"{title}.jpg"
        img.save(cover_path, "JPEG", quality=95)
        logger.info(f"文字封面已生成: {cover_path}")
        return cover_path
    except Exception as e:
        logger.error(f"生成文字封面失败: {e}")
        return None


def upload_file(access_token, env_id, file_path, cloud_path):
    with open(file_path, "rb") as f:
        file_content = base64.b64encode(f.read()).decode()

    url = "https://api.weixin.qq.com/tcb/clouduploadfile"
    payload = {"env": env_id, "path": "/tmp/upload", "cloudPath": cloud_path, "fileContent": file_content}

    resp = httpx.post(url, json=payload, timeout=180)
    result = resp.json()

    if result.get("errcode") == 0:
        file_id = result.get("file_id", "")
        logger.info(f"上传成功: {file_id}")
        return f"cloud://{env_id}/{cloud_path}"
    else:
        logger.error(f"上传失败: {result}")
        return None


def import_book(access_token, env_id, data_obj):
    data_str = json.dumps(data_obj, ensure_ascii=False)
    query = f'db.collection("books").add({{data: {data_str}}}'

    url = f"https://api.weixin.qq.com/tcb/databaseadd?access_token={access_token}"
    resp = httpx.post(url, json={"env": env_id, "query": query}, timeout=30)
    result = resp.json()

    if result.get("errcode") == 0:
        logger.info(f"导入成功")
        return result.get("id_list", [None])[0]
    else:
        logger.error(f"导入失败: {result}")
        return None


def gen_audio(text, output_path):
    import edge_tts

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    audo_dir = OUTPUT_DIR / "audios"
    audo_dir.mkdir(parents=True, exist_ok=True)

    try:
        communicate = edge_tts.Communicate(text, "zh-CN-XiaoxiaoNeural")
        communicate.save_sync(str(output_path))
        logger.info(f"音频生成成功: {output_path}")
        return output_path
    except Exception as e:
        logger.error(f"生成音频失败: {e}")
        return None


def main():
    logger.info("=" * 50)
    logger.info("开始生成: 杀死一只知更鸟")
    logger.info("=" * 50)

    load_env()
    app_id = os.environ.get("WECHAT_APP_ID")
    secret = os.environ.get("WECHAT_SECRET")
    env_id = os.environ.get("WECHAT_ENV_ID")

    if not all([app_id, secret, env_id]):
        logger.error("缺少环境变量")
        return

    # Step 1: 生成讲解稿
    logger.info("\n--- Step 1: 生成讲解稿 ---")
    script = generate_script()
    if not script:
        script = "这是一本关于种族歧视和正义的经典小说，作者哈珀·李通过一个小镇上的案件，展现了人性的光明与黑暗。"

    script_file = OUTPUT_DIR / "data" / f"{BOOK_INFO['title']}_script.txt"
    script_file.parent.mkdir(parents=True, exist_ok=True)
    with open(script_file, "w", encoding="utf-8") as f:
        f.write(script)
    logger.info(f"保存讲解稿: {script_file}")

    # Step 2: 生成音频
    logger.info("\n--- Step 2: 生成音频 ---")
    audio_path = OUTPUT_DIR / "audios" / f"{BOOK_INFO['title']}.mp3"
    gen_audio(script, audio_path)

    # Step 3: 下载/生成封面
    logger.info("\n--- Step 3: 封面处理 ---")
    cover_path = download_cover()

    # Step 4: 上传云存储
    logger.info("\n--- Step 4: 上传云存储 ---")
    access_token = get_access_token()
    logger.info("Token获取成功")

    audio_file_id = None
    if audio_path.exists():
        audio_file_id = upload_file(access_token, env_id, str(audio_path), f"audios/{BOOK_INFO['title']}.mp3")

    cover_file_id = None
    if cover_path and Path(cover_path).exists():
        cover_file_id = upload_file(access_token, env_id, str(cover_path), f"covers/{BOOK_INFO['title']}.jpg")

    # Step 5: 导入数据库
    logger.info("\n--- Step 5: 导入云数据库 ---")
    timestamp = int(time.time() * 1000)

    data_obj = {
        "title": BOOK_INFO["title"],
        "author": BOOK_INFO["author"],
        "category": "文学",
        "intro": BOOK_INFO["intro"],
        "script": script,
        "scriptLength": len(script),
        "quotes": BOOK_INFO["quotes"],
        "quotesCount": len(BOOK_INFO["quotes"]),
        "audioFileId": audio_file_id or "",
        "audioUrl": audio_file_id or "",
        "coverUrl": cover_file_id or "",
        "coverColor": BOOK_INFO["coverColor"],
        "duration": "00:05:00",
        "isGenerated": True,
        "isPublished": True,
        "isHot": False,
        "createTime": timestamp,
        "updateTime": timestamp,
    }

    book_id = import_book(access_token, env_id, data_obj)

    logger.info("\n" + "=" * 50)
    logger.info("生成完成!")
    logger.info(f"  讲解稿: {script_file}")
    logger.info(f"  音频: {audio_path}")
    logger.info(f"  封面: {cover_path}")
    logger.info(f"  数据库ID: {book_id}")
    logger.info("=" * 50)

    # 导出Excel配置
    excel_data = {"书名": [BOOK_INFO["title"]], "音频FileID": [audio_file_id or ""], "封面FileID": [cover_file_id or ""]}
    excel_file = OUTPUT_DIR / "test_mockingbird.xlsx"
    pd.DataFrame(excel_data).to_excel(excel_file, index=False)
    logger.info(f"\n导出Excel配置: {excel_file}")


if __name__ == "__main__":
    main()