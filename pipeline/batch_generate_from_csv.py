#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
批量从CSV生成书籍
- 读取enhanced CSV管理表
- 比对是否已导入
- 未导入的自动生成讲解稿/音频/封面/上传/导入数据库
- 支持断点续传
"""

import os
import sys
import json
import time
import logging
import base64
import random
import httpx
import pandas as pd
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).parent.parent
PIPELINE_DIR = Path(__file__).parent
OUTPUT_DIR = PIPELINE_DIR / "output"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


# 封面背景色配置
COVER_COLORS = [
    "#4A90A4", "#5D8AA8", "#6B8E8E", "#708090", "#778899",
    "#2F4F4F", "#483D8B", "#6A5ACD", "#7B68EE", "#9370DB",
    "#8B4789", "#CD5C5C", "#B8860B", "#DAA520", "#D2691E",
    "#A0522D", "#8B4513", "#6B8E23", "#556B2F", "#2E8B57",
]


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


def escape_str(s):
    """JSON字符串转义"""
    s = str(s)
    s = s.replace("\\", "\\\\")
    s = s.replace('"', '\\"')
    s = s.replace("\n", " ")
    s = s.replace("\r", " ")
    s = s.replace("\t", " ")
    # 替换中文引号为英文引号
    s = s.replace('"', '"').replace('"', '"')
    s = s.replace(''', "'").replace(''', "'")
    return s


def generate_script(title, author, category):
    """使用MiniMax API生成讲解稿"""
    from anthropic import Anthropic

    client = Anthropic(
        api_key=os.environ.get("ANTHROPIC_API_KEY"),
        base_url=os.environ.get("ANTHROPIC_BASE_URL", "https://api.minimaxi.com/anthropic"),
    )

    prompt = f"""请为《{title}》生成一段4200字左右的书籍讲解稿。

书籍信息：
- 书名：{title}
- 作者：{author if author else '未知'}
- 分类：{category}

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
        for block in msg.content:
            if hasattr(block, 'text'):
                script = block.text.strip()
                break
            elif hasattr(block, 'type') and block.type == 'thinking':
                continue
        else:
            script = str(msg.content)

        logger.info(f"  讲解稿生成成功 ({len(script)} 字)")
        return script
    except Exception as e:
        logger.error(f"  生成讲解稿失败: {type(e).__name__}: {e}")
        return None


def generate_text_cover(title, author, output_dir, color=None):
    """生成纯色+文字的简易封面"""
    try:
        from PIL import Image, ImageDraw, ImageFont

        color = color or random.choice(COVER_COLORS)
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
        if author:
            try:
                font_small = ImageFont.truetype("C:/Windows/Fonts/simhei.ttf", 28)
            except:
                font_small = font
            bbox = draw.textbbox((0, 0), author, font=font_small)
            author_width = bbox[2] - bbox[0]
            draw.text(((400 - author_width)//2, y + 10), author, fill="#FFFFFFCC", font=font_small)

        cover_path = output_dir / f"{title}.jpg"
        img.save(cover_path, "JPEG", quality=95)
        logger.info(f"  文字封面已生成: {cover_path}")
        return cover_path, color
    except Exception as e:
        logger.error(f"  生成文字封面失败: {e}")
        return None, None


def download_cover(title, douban_id=None):
    """下载封面，失败时生成纯色文字封面"""
    if douban_id:
        urls_to_try = [
            f"https://img2.douban.com/view/material_raw/public/p{douban_id}.jpg",
            f"https://img9.douban.com/view/material_raw/public/p{douban_id}.jpg",
        ]
    else:
        urls_to_try = []

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    covers_dir = OUTPUT_DIR / "covers"
    covers_dir.mkdir(parents=True, exist_ok=True)
    cover_path = covers_dir / f"{title}.jpg"

    for cover_url in urls_to_try:
        try:
            logger.info(f"  尝试下载封面: {cover_url}")
            resp = httpx.get(cover_url, timeout=30, follow_redirects=True)
            if resp.status_code == 200 and len(resp.content) > 5000:
                with open(cover_path, "wb") as f:
                    f.write(resp.content)
                logger.info(f"  封面下载成功: {len(resp.content)} bytes")
                return cover_path, None
        except Exception as e:
            logger.warning(f"  下载失败: {e}")
            continue

    # 下载失败，生成纯色文字封面
    logger.info("  自动生成纯色文字封面...")
    return generate_text_cover(title, None, covers_dir)


def gen_audio(text, title, output_dir):
    """使用edge-tts生成音频"""
    import edge_tts

    output_dir.mkdir(parents=True, exist_ok=True)
    audio_dir = output_dir / "audios"
    audio_dir.mkdir(parents=True, exist_ok=True)

    try:
        communicate = edge_tts.Communicate(text, "zh-CN-XiaoxiaoNeural")
        audio_path = audio_dir / f"{title}.mp3"
        communicate.save_sync(str(audio_path))
        logger.info(f"  音频生成成功: {audio_path}")
        return audio_path
    except Exception as e:
        logger.error(f"  生成音频失败: {e}")
        return None


def upload_file(access_token, env_id, file_path, cloud_path):
    """上传文件到微信云存储（正确两步流程）"""
    if not os.path.exists(file_path):
        logger.warning(f"  文件不存在: {file_path}")
        return None

    # Step 1: 获取上传链接和凭证
    step1_url = f"https://api.weixin.qq.com/tcb/uploadfile?access_token={access_token}"
    payload1 = {"env": env_id, "path": cloud_path}

    try:
        resp1 = httpx.post(step1_url, json=payload1, timeout=30)
        result1 = resp1.json()
        if result1.get("errcode") != 0:
            logger.error(f"  获取上传链接失败: {result1}")
            return None

        upload_url = result1.get("url")
        token = result1.get("token")
        authorization = result1.get("authorization")
        cos_file_id = result1.get("cos_file_id")
        file_id = result1.get("file_id", "")
        logger.info(f"  获取上传链接成功: {file_id[:30]}...")

        # Step 2: POST文件到上传URL（multipart/form-data）
        with open(file_path, "rb") as f:
            file_content = f.read()

        files = {
            "key": (None, cloud_path),
            "Signature": (None, authorization),
            "x-cos-security-token": (None, token),
            "x-cos-meta-fileid": (None, cos_file_id),
            "file": (os.path.basename(file_path), file_content),
        }

        resp2 = httpx.post(upload_url, files=files, timeout=180)
        logger.info(f"  上传响应状态: {resp2.status_code}")
        if resp2.status_code in [200, 204]:
            logger.info(f"  上传成功: {file_id}")
            return file_id
        else:
            logger.error(f"  文件上传失败: {resp2.status_code} {resp2.text[:200]}")
            return None

    except Exception as e:
        logger.error(f"  上传异常: {type(e).__name__}: {e}")
        return None


def import_book(access_token, env_id, data_obj):
    """导入书籍到云数据库"""
    data_str = json.dumps(data_obj, ensure_ascii=False)
    query = f'db.collection("books").add({{data: {data_str}}})'

    url = f"https://api.weixin.qq.com/tcb/databaseadd?access_token={access_token}"
    try:
        resp = httpx.post(url, json={"env": env_id, "query": query}, timeout=30)
        result = resp.json()
        if result.get("errcode") == 0:
            book_id = result.get("id_list", [None])[0]
            logger.info(f"  导入数据库成功: {book_id}")
            return book_id
        else:
            logger.error(f"  导入数据库失败: {result}")
            return None
    except Exception as e:
        logger.error(f"  导入异常: {e}")
        return None


def update_csv(csv_path, title, data):
    """更新CSV中对应书籍的状态"""
    try:
        df = pd.read_csv(csv_path, encoding='utf-8')
        idx = df[df['书名'] == title].index
        if len(idx) > 0:
            for key, value in data.items():
                if key in df.columns:
                    df.at[idx[0], key] = value
            df.to_csv(csv_path, index=False, encoding='utf-8')
            logger.info(f"  CSV已更新: {title}")
    except Exception as e:
        logger.error(f"  更新CSV失败: {e}")


def process_single_book(row, csv_path, access_token, env_id, output_dir):
    """处理单本书籍的完整流程"""
    title = str(row.get('书名', '')).strip()
    author = str(row.get('作者', '')).strip() if pd.notna(row.get('作者')) else ''
    category = str(row.get('分类', '文学')).strip()
    is_imported = str(row.get('是否导入', '否')).strip() == '是'

    if is_imported:
        logger.info(f"[{title}] 已导入，跳过")
        return True

    logger.info(f"\n{'='*50}")
    logger.info(f"开始处理: {title}")
    logger.info(f"{'='*50}")

    timestamp = int(time.time() * 1000)
    errors = []

    # Step 1: 生成讲解稿
    logger.info("--- Step 1: 生成讲解稿 ---")
    script = generate_script(title, author, category)
    if not script:
        script = f"《{title}》是一本{category}类书籍，由{author if author else '未知'}编写。"
        errors.append("讲解稿生成失败，使用默认文本")

    # 保存讲解稿
    script_file = output_dir / "data" / f"{title}_script.txt"
    script_file.parent.mkdir(parents=True, exist_ok=True)
    with open(script_file, "w", encoding="utf-8") as f:
        f.write(script)

    # Step 2: 生成音频
    logger.info("--- Step 2: 生成音频 ---")
    audio_path = gen_audio(script, title, output_dir)

    # Step 3: 生成/下载封面
    logger.info("--- Step 3: 封面处理 ---")
    cover_path, cover_color = download_cover(title)

    # Step 4: 上传云存储
    logger.info("--- Step 4: 上传云存储 ---")
    # 使用拼音替代中文，避免cloudPath编码问题
    import re
    # 只保留ASCII字母数字和下划线
    safe_title = re.sub(r'[^a-zA-Z0-9_\-]', '_', title)
    audio_file_id = None
    if audio_path and audio_path.exists():
        audio_file_id = upload_file(access_token, env_id, str(audio_path), f"audios/{safe_title}.mp3")

    cover_file_id = None
    if cover_path and os.path.exists(str(cover_path)):
        cover_file_id = upload_file(access_token, env_id, str(cover_path), f"covers/{safe_title}.jpg")

    # Step 5: 导入数据库
    logger.info("--- Step 5: 导入云数据库 ---")
    duration = "00:05:00"
    if audio_path and audio_path.exists():
        import wave
        try:
            with wave.open(str(audio_path), 'rb') as w:
                frames = w.getnframes()
                rate = w.getframerate()
                duration_sec = frames / float(rate)
                mins, secs = divmod(int(duration_sec), 60)
                hours, mins = divmod(mins, 60)
                duration = f"{hours:02d}:{mins:02d}:{secs:02d}"
        except:
            pass

    # 处理讲解稿中的特殊字符，避免JSON解析错误
    safe_script = escape_str(script[:500]) if script else ""

    data_obj = {
        "title": title,
        "author": author if author else "未知",
        "category": category,
        "intro": f"《{title}》是{category}类书籍",
        "script": safe_script,
        "scriptLength": len(script) if script else 0,
        "quotes": [],  # 暂不生成金句
        "quotesCount": 0,
        "audioFileId": audio_file_id or "",
        "audioUrl": audio_file_id or "",
        "coverUrl": cover_file_id or "",
        "coverColor": cover_color or "#4A90A4",
        "duration": duration,
        "isGenerated": True,
        "isPublished": True,
        "isHot": False,
        "createTime": timestamp,
        "updateTime": timestamp,
    }

    book_id = import_book(access_token, env_id, data_obj)

    # Step 6: 更新CSV
    logger.info("--- Step 6: 更新CSV ---")
    update_data = {
        '是否导入': '是' if book_id else '否',
        '导入时间': datetime.now().strftime('%Y-%m-%d %H:%M') if book_id else '',
        '数据库ID': book_id if book_id else '',
        '封面FileID': cover_file_id if cover_file_id else '',
        '音频FileID': audio_file_id if audio_file_id else '',
        '讲解稿': str(len(script)) + '字' if script else '',
        '错误信息': '; '.join(errors) if errors else '',
    }
    update_csv(csv_path, title, update_data)

    if book_id:
        logger.info(f"✓ {title} 处理完成!")
        return True
    else:
        logger.error(f"✗ {title} 处理失败")
        return False


def main():
    import argparse
    parser = argparse.ArgumentParser(description='批量从CSV生成书籍')
    parser.add_argument('--csv', default=None, help='CSV文件路径')
    parser.add_argument('--limit', type=int, default=5, help='限制生成数量(默认5)')
    parser.add_argument('--start', type=int, default=0, help='起始位置')
    args = parser.parse_args()

    load_env()

    # 配置检查
    app_id = os.environ.get("WECHAT_APP_ID")
    secret = os.environ.get("WECHAT_SECRET")
    env_id = os.environ.get("WECHAT_ENV_ID")

    if not all([app_id, secret, env_id]):
        logger.error("缺少必要的环境变量 WECHAT_APP_ID, WECHAT_SECRET, WECHAT_ENV_ID")
        return

    # CSV路径
    if args.csv:
        csv_path = Path(args.csv)
    else:
        csv_path = BASE_DIR / "data_source" / "book_list_500_enhanced.csv"

    if not csv_path.exists():
        logger.error(f"CSV文件不存在: {csv_path}")
        return

    # 读取CSV
    df = pd.read_csv(csv_path, encoding='utf-8')
    logger.info(f"Loaded {len(df)} books from CSV")

    # 获取token
    access_token = get_access_token()
    logger.info("Token获取成功")

    # 统计未导入的书籍
    not_imported = df[df['是否导入'] != '是']
    logger.info(f"待处理书籍: {len(not_imported)} 本")

    # 处理
    output_dir = OUTPUT_DIR
    success_count = 0
    fail_count = 0

    for i, (idx, row) in enumerate(not_imported.iterrows()):
        if i < args.start:
            continue
        if i >= args.start + args.limit:
            break

        try:
            ok = process_single_book(row, csv_path, access_token, env_id, output_dir)
            if ok:
                success_count += 1
            else:
                fail_count += 1
        except Exception as e:
            logger.error(f"处理异常: {type(e).__name__}: {e}")
            fail_count += 1
            # 更新CSV错误信息
            update_csv(csv_path, str(row.get('书名', '')), {'错误信息': str(e)})

        # 间隔3秒，避免API限制
        if i < args.start + args.limit - 1:
            time.sleep(3)

    logger.info(f"\n{'='*50}")
    logger.info(f"批量生成完成!")
    logger.info(f"  成功: {success_count} 本")
    logger.info(f"  失败: {fail_count} 本")
    logger.info(f"{'='*50}")


if __name__ == "__main__":
    main()
