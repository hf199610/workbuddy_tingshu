#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""校验并修复书籍数据：金句数量和音频时长"""

import os, json, time, logging, httpx, re, csv
from pathlib import Path
from mutagen.mp3 import MP3

PIPELINE_DIR = Path(__file__).parent
OUTPUT_DIR = PIPELINE_DIR / "output"
CSV_FILE = PIPELINE_DIR.parent / "data_source" / "book_list_500_enhanced.csv"

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
    s = str(s)
    s = s.replace("\\", "\\\\")
    s = s.replace('"', '\\"')
    s = s.replace("\n", "\\n")
    s = s.replace("\r", "\\r")
    s = s.replace("\t", "\\t")
    s = s.replace('"', '"').replace('"', '"')
    s = s.replace(''', "'").replace(''', "'")
    return s


def generate_quotes(title, author, count=10):
    """生成多条金句（带重试机制）"""
    from anthropic import Anthropic
    client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"),
                       base_url=os.environ.get("ANTHROPIC_BASE_URL"))

    # 改进的prompt - 明确要求JSON数组格式
    prompt = f"""请为《{title}》（作者：{author}）生成{count}条经典金句。

请严格按以下JSON数组格式输出（不要包含任何其他内容）：
[
  {{"content": "金句内容1", "author": "作者或人物1"}},
  {{"content": "金句内容2", "author": "作者或人物2"}},
  {{"content": "金句内容3", "author": "作者或人物3"}}
]

要求：
1. 必须生成恰好{count}条金句
2. 每条金句不超过50字
3. 每条必须包含content和author两个字段
4. 只输出JSON数组，不要任何其他说明文字"""

    for attempt in range(3):
        try:
            msg = client.messages.create(
                model=os.environ.get("MINIMAX_MODEL", "MiniMax-M2.7"),
                max_tokens=4000,
                messages=[{"role": "user", "content": prompt}]
            )
            text = ""
            for block in msg.content:
                if hasattr(block, 'type') and block.type == 'text':
                    text = block.text.strip()
                    break
            else:
                text = str(msg.content)

            logger.info(f"API返回原始内容: {text[:500]}")

            # 尝试解析JSON
            # 先找数组部分 - 使用贪婪匹配避免提前终止
            import re
            # 匹配整个JSON数组
            matches = re.findall(r'\{[^{}]*\}', text)
            if len(matches) >= count:
                quotes = []
                for m in matches[:count]:
                    try:
                        q = json.loads(m)
                        if 'content' in q and 'author' in q:
                            quotes.append(q)
                    except:
                        pass
                if len(quotes) >= count:
                    logger.info(f"成功解析到{len(quotes)}条金句")
                    return quotes

            # 如果解析失败或数量不够，重试
            logger.warning(f"第{attempt+1}次尝试失败，继续重试...")

        except Exception as e:
            logger.error(f"第{attempt+1}次异常: {e}")
            time.sleep(5)

    # 所有重试都失败，返回默认值
    return [{"content": f"《{title}》中的经典句子。", "author": author}]


def gen_audio_male(text, output_path):
    """生成男声音频（带重试）"""
    import edge_tts

    # 如果文本太长，分段处理
    MAX_CHUNK = 2980
    if len(text) <= MAX_CHUNK:
        return _gen_audio_single(text, output_path)

    # 分段生成
    chunks = []
    para_list = text.split('\n')
    current = []
    current_len = 0

    for para in para_list:
        para_len = len(para)
        if current_len + para_len > MAX_CHUNK and current:
            chunks.append('\n'.join(current))
            current = []
            current_len = 0
        current.append(para)
        current_len += para_len

    if current:
        chunks.append('\n'.join(current))

    logger.info(f"文本过长，分{len(chunks)}段生成音频")

    # 逐段生成并合并
    import io
    from pydub import AudioSegment

    output_path.parent.mkdir(parents=True, exist_ok=True)

    combined = AudioSegment.empty()
    for i, chunk in enumerate(chunks):
        chunk_file = output_path.parent / f"temp_chunk_{i}.mp3"
        result = _gen_audio_single(chunk, chunk_file)
        if result:
            combined += AudioSegment.from_mp3(str(chunk_file))
            chunk_file.unlink(missing_ok=True)
        time.sleep(1)  # 避免频率限制

    combined.export(str(output_path), format="mp3")
    logger.info(f"音频合并完成: {output_path}")
    return output_path


def _gen_audio_single(text, output_path):
    """单个音频生成"""
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


def update_book_in_db(access_token, env_id, book_id, data):
    """更新数据库记录"""
    # 先删除旧记录
    del_query = f'db.collection("books").doc("{book_id}").remove()'
    httpx.post(f"https://api.weixin.qq.com/tcb/databasedelete?access_token={access_token}",
               json={"env": env_id, "query": del_query}, timeout=30)

    # 添加新记录
    data_str = json.dumps(data, ensure_ascii=False)
    add_query = f'db.collection("books").add({{data: {data_str}}})'
    resp = httpx.post(f"https://api.weixin.qq.com/tcb/databaseadd?access_token={access_token}",
                      json={"env": env_id, "query": add_query}, timeout=60)
    result = resp.json()
    if result.get("errcode") == 0:
        return result.get("id_list", [None])[0]
    logger.error(f"更新失败: {result}")
    return None


def main():
    logger.info("=" * 60)
    logger.info("校验并修复书籍数据")
    logger.info("=" * 60)

    load_env()
    env_id = os.environ.get("WECHAT_ENV_ID")

    # 获取数据库中的书籍
    access_token = get_access_token()
    query = 'db.collection("books").limit(100).get()'
    resp = httpx.post(f"https://api.weixin.qq.com/tcb/databasequery?access_token={access_token}",
                      json={"env": env_id, "query": query}, timeout=30)
    docs = resp.json().get("data", [])

    logger.info(f"数据库中共有 {len(docs)} 本书")

    # 需要修复的书籍
    books_to_fix = []

    for doc in docs:
        book = json.loads(doc)
        title = book.get("title", "未知")
        book_id = book.get("_id")
        quotes = book.get("quotes", [])
        duration = book.get("duration", "00:05:00")
        script = book.get("script", "")

        issues = []

        # 检查金句数量
        if len(quotes) < 10:
            issues.append(f"金句不足({len(quotes)}条 < 10条)")

        # 检查音频时长（如果字数>5000但时长<=5分钟，说明异常）
        script_len = book.get("scriptLength", 0)
        if script_len > 5000 and duration == "00:05:00":
            issues.append(f"音频时长异常({duration})")

        if issues:
            books_to_fix.append({
                "book": book,
                "book_id": book_id,
                "issues": issues,
                "need_audio": script_len > 5000 and duration == "00:05:00",
                "need_quotes": len(quotes) < 10
            })

    if not books_to_fix:
        logger.info("所有书籍数据都正常，无需修复！")
        return

    logger.info(f"\n需要修复的书籍: {len(books_to_fix)} 本")
    for bf in books_to_fix:
        logger.info(f"  - {bf['book'].get('title')}: {'; '.join(bf['issues'])}")

    # 逐个修复
    for i, bf in enumerate(books_to_fix, 1):
        book = bf["book"]
        book_id = bf["book_id"]
        title = book.get("title")
        author = book.get("author")
        script = book.get("script", "")

        logger.info(f"\n{'='*60}")
        logger.info(f"【第{i}/{len(books_to_fix)}本】修复: {title}")
        logger.info(f"{'='*60}")

        try:
            # 1. 修复金句
            if bf["need_quotes"]:
                logger.info("\n--- 修复金句 ---")
                # 先尝试从本地读取已生成的讲解稿
                script_file = OUTPUT_DIR / "data" / f"{title}_script.txt"
                if script_file.exists():
                    with open(script_file, "r", encoding="utf-8") as f:
                        script = f.read()
                    logger.info(f"从本地读取讲解稿: {len(script)} 字")

                quotes = generate_quotes(title, author, count=10)
                if not quotes:
                    quotes = [{"content": f"这是《{title}》中的一句经典台词。", "author": author}]
                logger.info(f"金句已生成: {len(quotes)} 条")
            else:
                quotes = book.get("quotes", [])

            # 2. 修复音频
            new_audio_file_id = None
            new_duration = book.get("duration")

            if bf["need_audio"]:
                logger.info("\n--- 修复音频 ---")
                audio_path = OUTPUT_DIR / "audios" / f"{title}_male_fixed.mp3"

                # 读取脚本内容
                script_file = OUTPUT_DIR / "data" / f"{title}_script.txt"
                if not script_file.exists():
                    logger.warning(f"未找到讲解稿文件: {script_file}，跳过音频修复")
                else:
                    with open(script_file, "r", encoding="utf-8") as f:
                        script = f.read()

                    result = gen_audio_male(script, audio_path)
                    if result:
                        # 上传新音频
                        token = get_access_token()
                        new_audio_file_id = upload_file(token, env_id, str(audio_path), f"audios/{title}_male_fixed.mp3")
                        new_duration = get_audio_duration(audio_path)
                        logger.info(f"新音频已上传: {new_audio_file_id}, 时长: {new_duration}")
                    else:
                        logger.warning("音频修复失败，保留原音频")

            # 3. 更新数据库
            logger.info("\n--- 更新数据库 ---")
            token = get_access_token()

            data_obj = {
                "title": book.get("title"),
                "author": book.get("author"),
                "category": book.get("category"),
                "intro": escape_str(book.get("intro", "")),
                "script": escape_str(script) if script else book.get("script"),
                "scriptLength": book.get("scriptLength", len(script) if script else 0),
                "quotes": quotes,
                "quotesCount": len(quotes),
                "audioFileId": new_audio_file_id or book.get("audioFileId", ""),
                "audioUrl": new_audio_file_id or book.get("audioUrl", ""),
                "coverUrl": book.get("coverUrl", ""),
                "coverColor": book.get("coverColor", "#6A5ACD"),
                "duration": new_duration,
                "isGenerated": True,
                "isPublished": True,
                "isHot": book.get("isHot", False),
                "createTime": book.get("createTime", int(time.time() * 1000)),
                "updateTime": int(time.time() * 1000),
            }

            new_id = update_book_in_db(token, env_id, book_id, data_obj)
            logger.info(f"数据库已更新，新ID: {new_id}")

            logger.info(f"\n✅ {title} 修复完成!")
            logger.info(f"   金句: {len(quotes)} 条")
            logger.info(f"   音频时长: {new_duration}")

            # 每本修复后等待一下
            if i < len(books_to_fix):
                time.sleep(15)

        except Exception as e:
            logger.error(f"修复 {title} 时出错: {e}")
            import traceback
            traceback.print_exc()
            continue

    logger.info("\n" + "=" * 60)
    logger.info("全部修复完成!")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
