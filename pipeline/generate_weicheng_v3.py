#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""重新生成围城 v3 - 修复字数和token问题"""

import os, json, time, logging, httpx
from pathlib import Path
from mutagen.mp3 import MP3

PIPELINE_DIR = Path(__file__).parent
OUTPUT_DIR = PIPELINE_DIR / "output"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def load_env():
    for env_path in [PIPELINE_DIR / ".env", PIPELINE_DIR.parent / ".env"]:
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
    resp = httpx.get(f"https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={app_id}&secret={secret}", timeout=30)
    return resp.json()["access_token"]


def escape_str(s):
    s = str(s).replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ").replace("\r", " ").replace("\t", " ")
    s = s.replace('"', '"').replace('"', '"').replace(''', "'").replace(''', "'")
    return s


def generate_script():
    from anthropic import Anthropic
    client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"),
                       base_url=os.environ.get("ANTHROPIC_BASE_URL"))

    prompt = """请为《围城》（作者：钱钟书）生成一段4200-4500字的书籍讲解稿。

要求：
1. 详细生动地介绍写作背景、情节、人物、主题思想
2. 语言通俗易懂，适合听书场景
3. 字数严格控制在4200-4500字之间，不能少于4000字，不能超过5000字
4. 只输出讲解稿内容，不要其他说明"""

    msg = client.messages.create(model=os.environ.get("MINIMAX_MODEL", "MiniMax-M2.7"),
                                  max_tokens=8000, messages=[{"role": "user", "content": prompt}])
    for block in msg.content:
        if hasattr(block, 'type') and block.type == 'text':
            text = block.text.strip()
            break
    else:
        text = str(msg.content)

    # 截取前4500个字符（中文约4500字）
    if len(text) > 4500:
        text = text[:4500]
        # 确保在句子结尾截断
        last_period = max(text.rfind('。'), text.rfind('！'), text.rfind('？'))
        if last_period > 4000:
            text = text[:last_period+1]
    return text


def generate_quotes():
    from anthropic import Anthropic
    client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"),
                       base_url=os.environ.get("ANTHROPIC_BASE_URL"))

    prompt = """请为《围城》（作者：钱钟书）生成5条经典金句。
要求：
1. 每条金句不超过50字
2. 每条附上出处人物（如"钱钟书"或"方鸿渐"）
3. 只输出JSON数组，不要其他说明
格式：[{"content": "金句内容", "author": "出处人物"}]"""

    msg = client.messages.create(model=os.environ.get("MINIMAX_MODEL", "MiniMax-M2.7"),
                                  max_tokens=2000, messages=[{"role": "user", "content": prompt}])
    text = ""
    for block in msg.content:
        if hasattr(block, 'type') and block.type == 'text':
            text = block.text.strip()
            break
    else:
        text = str(msg.content)

    import re
    match = re.search(r'\[.*?\]', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except:
            pass
    return []


def gen_audio_male(text, output_path):
    import edge_tts
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        communicate = edge_tts.Communicate(text, "zh-CN-YunxiNeural")
        communicate.save_sync(str(output_path))
        logger.info(f"音频生成成功: {output_path}")
        return output_path
    except Exception as e:
        logger.error(f"生成音频失败: {e}")
        return None


def get_audio_duration(path):
    try:
        audio = MP3(str(path))
        total_sec = int(audio.info.length)
        mins, secs = divmod(total_sec, 60)
        hours, mins = divmod(mins, 60)
        return f"{hours:02d}:{mins:02d}:{secs:02d}"
    except:
        return "00:05:00"


def generate_cover(title, author, output_path, color="#6A5ACD"):
    from PIL import Image, ImageDraw, ImageFont
    try:
        img = Image.new("RGB", (400, 600), color=color)
        draw = ImageDraw.Draw(img)
        draw.rectangle([20, 20, 380, 580], outline="white", width=3)
        try:
            font = ImageFont.truetype("C:/Windows/Fonts/simhei.ttf", 40)
        except:
            font = ImageFont.load_default()
        lines = [title[i:i+6] for i in range(0, len(title), 6)]
        y = 250
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            x = (400 - (bbox[2]-bbox[0])) // 2
            draw.text((x, y), line, fill="white", font=font)
            y += 60
        bbox = draw.textbbox((0, 0), author, font=font)
        draw.text(((400-(bbox[2]-bbox[0]))//2, y+20), author, fill="#FFFFFFCC", font=font)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(output_path, "JPEG", quality=95)
        return output_path
    except Exception as e:
        logger.error(f"生成封面失败: {e}")
        return None


def upload_file(access_token, env_id, file_path, cloud_path):
    if not os.path.exists(file_path):
        return None
    step1_url = f"https://api.weixin.qq.com/tcb/uploadfile?access_token={access_token}"
    resp1 = httpx.post(step1_url, json={"env": env_id, "path": cloud_path}, timeout=30)
    result1 = resp1.json()
    if result1.get("errcode") != 0:
        logger.error(f"获取上传链接失败: {result1}")
        return None

    with open(file_path, "rb") as f:
        file_content = f.read()
    files = {
        "key": (None, cloud_path),
        "Signature": (None, result1.get("authorization")),
        "x-cos-security-token": (None, result1.get("token")),
        "x-cos-meta-fileid": (None, result1.get("cos_file_id")),
        "file": (os.path.basename(file_path), file_content),
    }
    resp2 = httpx.post(result1.get("url"), files=files, timeout=180)
    if resp2.status_code in [200, 204]:
        return result1.get("file_id", "")
    logger.error(f"上传失败: {resp2.status_code}")
    return None


def update_book(access_token, env_id, book_id, data):
    del_query = f'db.collection("books").doc("{book_id}").remove()'
    httpx.post(f"https://api.weixin.qq.com/tcb/databasedelete?access_token={access_token}",
               json={"env": env_id, "query": del_query}, timeout=30)

    data_str = json.dumps(data, ensure_ascii=False)
    add_query = f'db.collection("books").add({{data: {data_str}}})'
    resp = httpx.post(f"https://api.weixin.qq.com/tcb/databaseadd?access_token={access_token}",
                      json={"env": env_id, "query": add_query}, timeout=30)
    result = resp.json()
    if result.get("errcode") == 0:
        return result.get("id_list", [None])[0]
    logger.error(f"导入失败: {result}")
    return None


def clear_quotes_collection(access_token, env_id):
    query = 'db.collection("quotes_collection").limit(100).get()'
    resp = httpx.post(f"https://api.weixin.qq.com/tcb/databasequery?access_token={access_token}",
                      json={"env": env_id, "query": query}, timeout=30)
    docs = resp.json().get("data", [])
    logger.info(f"quotes_collection 当前 {len(docs)} 条")
    deleted = 0
    for doc in docs:
        doc_id = json.loads(doc).get("_id")
        if doc_id:
            del_q = f'db.collection("quotes_collection").doc("{doc_id}").remove()'
            r = httpx.post(f"https://api.weixin.qq.com/tcb/databasedelete?access_token={access_token}",
                           json={"env": env_id, "query": del_q}, timeout=30)
            if r.json().get("errcode") == 0:
                deleted += 1
    logger.info(f"已清空 {deleted} 条")
    return deleted


BOOK_INFO = {
    "title": "围城",
    "author": "钱钟书",
    "category": "经典名著",
    "coverColor": "#6A5ACD",
    "intro": "《围城》是中国著名学者钱钟书创作的长篇小说，首次出版于1947年。小说以抗战初期为背景，讲述留学生方鸿渐回国后的爱情与职场经历。书中通过方鸿渐与苏文纨、唐晓芙、孙柔嘉的情感纠葛，揭示了人生的困境。小说语言幽默辛辣，讽刺深刻，被誉为中国现代文学经典之作。",
}


def main():
    logger.info("=" * 50)
    logger.info("重新生成围城 v3")
    logger.info("=" * 50)

    load_env()
    env_id = os.environ.get("WECHAT_ENV_ID")
    title = BOOK_INFO["title"]

    # Step 1: 生成讲解稿
    logger.info("\n--- Step 1: 生成讲解稿 ---")
    script = generate_script()
    script_file = OUTPUT_DIR / "data" / f"{title}_script_v3.txt"
    script_file.parent.mkdir(parents=True, exist_ok=True)
    with open(script_file, "w", encoding="utf-8") as f:
        f.write(script)
    logger.info(f"讲解稿: {len(script)} 字")

    # Step 2: 生成金句
    logger.info("\n--- Step 2: 生成金句 ---")
    quotes = generate_quotes()
    if not quotes:
        quotes = [
            {"content": "婚姻像围城，外面的人想进去，里面的人想出来。", "author": "钱钟书"},
            {"content": "流言这东西，比流感蔓延的速度更快。", "author": "钱钟书"},
            {"content": "打消已起的念头仿佛跟女人怀孕要打胎一样的难受。", "author": "方鸿渐"},
            {"content": "上了年纪的人动了爱情，就如同老房子着火，不可救药。", "author": "钱钟书"},
            {"content": "天下只有两种人。比如一串葡萄到手，一种人挑最好的先吃。", "author": "钱钟书"},
        ]
    logger.info(f"金句: {len(quotes)} 条")

    # Step 3: 生成男声音频
    logger.info("\n--- Step 3: 生成男声音频 ---")
    audio_path = OUTPUT_DIR / "audios" / f"{title}_male_v3.mp3"
    gen_audio_male(script, audio_path)

    # Step 4: 生成封面
    logger.info("\n--- Step 4: 生成封面 ---")
    cover_path = OUTPUT_DIR / "covers" / f"{title}_v3.jpg"
    generate_cover(title, BOOK_INFO["author"], cover_path, BOOK_INFO["coverColor"])

    # Step 5: 获取新token并上传
    logger.info("\n--- Step 5: 上传云存储 ---")
    access_token = get_access_token()
    audio_file_id = upload_file(access_token, env_id, str(audio_path), f"audios/{title}_male_v3.mp3") if audio_path.exists() else None
    cover_file_id = upload_file(access_token, env_id, str(cover_path), f"covers/{title}_v3.jpg") if cover_path and cover_path.exists() else None

    # Step 6: 清空 quotes_collection
    logger.info("\n--- Step 6: 清空 quotes_collection ---")
    clear_quotes_collection(access_token, env_id)

    # Step 7: 更新数据库（用新token）
    logger.info("\n--- Step 7: 更新数据库 ---")
    access_token = get_access_token()  # 重新获取token
    duration = get_audio_duration(audio_path) if audio_path.exists() else "00:05:00"
    timestamp = int(time.time() * 1000)

    data_obj = {
        "title": title,
        "author": BOOK_INFO["author"],
        "category": BOOK_INFO["category"],
        "intro": escape_str(BOOK_INFO["intro"]),
        "script": escape_str(script),
        "scriptLength": len(script),
        "quotes": quotes,
        "quotesCount": len(quotes),
        "audioFileId": audio_file_id or "",
        "audioUrl": audio_file_id or "",
        "coverUrl": cover_file_id or "",
        "coverColor": BOOK_INFO["coverColor"],
        "duration": duration,
        "isGenerated": True,
        "isPublished": True,
        "isHot": False,
        "createTime": timestamp,
        "updateTime": timestamp,
    }

    book_id = update_book(access_token, env_id, "a54a659b6a141217009558865e5ddbf1", data_obj)

    logger.info("\n" + "=" * 50)
    logger.info("完成!")
    logger.info(f"  讲解稿: {len(script)} 字")
    logger.info(f"  金句: {len(quotes)} 条")
    logger.info(f"  音频时长: {duration}")
    logger.info(f"  音频FileID: {audio_file_id}")
    logger.info(f"  封面FileID: {cover_file_id}")
    logger.info(f"  数据库ID: {book_id}")
    logger.info("=" * 50)


if __name__ == "__main__":
    main()
