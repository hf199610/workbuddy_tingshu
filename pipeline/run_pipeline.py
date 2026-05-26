#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
一站式数据导入脚本
完整流程：爬取书籍 → 生成字幕 → 导入云数据库

使用方法:
  python run_pipeline.py                               # 完整流程（手动数据源+MiniMax）
  python run_pipeline.py --source douban               # 使用豆瓣爬取
  python run_pipeline.py --api doubao                  # 使用豆包API生成文稿
  python run_pipeline.py --skip-crawl                  # 跳过爬取，直接用已有数据
  python run_pipeline.py --skip-script                 # 跳过文稿生成
  python run_pipeline.py --skip-import                 # 跳过云导入（只生成数据）
  python run_pipeline.py --books "小王子,活着"          # 只处理指定书籍
  python run_pipeline.py --dry-run                     # 预览模式

输出:
  - 爬取数据: data_source/crawled_output.json
  - 文稿数据: data_source/step2_books_with_script.json
  - 导入数据: data_source/step4_for_database_import.json
  - 文稿文件: data_source/scripts/{书名}_script.txt
  - 金句文件: data_source/scripts/{书名}_quotes.txt
"""

import os
import sys
import json
import time
import logging
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

# 确保模块可导入
sys.path.insert(0, str(Path(__file__).parent))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)

# 路径配置
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data_source"
SCRIPTS_DIR = DATA_DIR / "scripts"


def load_env():
    """加载环境变量"""
    # 从 pipeline/.env
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        with open(env_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    # 处理 ${VAR} 格式的变量引用
                    if value.startswith('${') and value.endswith('}'):
                        ref_key = value[2:-1]
                        value = os.getenv(ref_key, "")
                    os.environ.setdefault(key.strip(), value.strip())

    # 从 miniprogram/.env
    mp_env = Path(__file__).parent.parent / "miniprogram" / ".env"
    if mp_env.exists():
        with open(mp_env, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ.setdefault(key.strip(), value.strip())


# ==================== 步骤1：爬取书籍 ====================
def step1_crawl(book_names: List[str], source: str = "manual") -> List[Dict]:
    """爬取书籍基础信息"""
    from crawl_books import crawl_books
    logger.info(f"\n{'═'*60}")
    logger.info(f"📦 步骤1：爬取书籍信息")
    logger.info(f"{'═'*60}")

    books = crawl_books(book_names, source=source)
    logger.info(f"✅ 步骤1完成：获取 {len(books)} 本书")

    # 保存中间结果
    output = DATA_DIR / "crawled_output.json"
    with open(output, 'w', encoding='utf-8') as f:
        json.dump(books, f, ensure_ascii=False, indent=2)

    return books


# ==================== 步骤2：生成字幕 ====================
def step2_generate_scripts(books: List[Dict], api: str = "minimax", dry_run: bool = False) -> List[Dict]:
    """生成字幕文稿"""
    from generate_scripts import generate_scripts
    logger.info(f"\n{'═'*60}")
    logger.info(f"📝 步骤2：生成字幕文稿 (API: {api if not dry_run else '模拟'})")
    logger.info(f"{'═'*60}")

    books = generate_scripts(books, api=api, dry_run=dry_run)
    logger.info(f"✅ 步骤2完成")

    # 保存中间结果
    output = DATA_DIR / "step2_books_with_script.json"
    with open(output, 'w', encoding='utf-8') as f:
        json.dump(books, f, ensure_ascii=False, indent=2)

    return books


# ==================== 步骤3：TTS音频（可选） ====================
def step3_generate_audio(books: List[Dict]) -> List[Dict]:
    """生成TTS音频（使用edge-tts）"""
    logger.info(f"\n{'═'*60}")
    logger.info(f"🎙️ 步骤3：生成TTS音频")
    logger.info(f"{'═'*60}")
    logger.info(f"⚠️ 注意：音频生成需要安装 edge-tts")
    logger.info(f"   安装命令: npm install -g edge-tts")
    logger.info(f"   本步骤为可选，跳过不影响数据导入")

    try:
        import subprocess

        for i, book in enumerate(books):
            if not book.get("script"):
                logger.info(f"[{i+1}/{len(books)}] ⏭️ 无文稿，跳过: 《{book.get('title')}》")
                continue

            title = book.get("title", "unknown")
            output_dir = DATA_DIR / "audio"
            output_dir.mkdir(parents=True, exist_ok=True)
            output_file = output_dir / f"{title}_audio.mp3"

            if output_file.exists():
                logger.info(f"[{i+1}/{len(books)}] ⏭️ 音频已存在: 《{title}》")
                book["audioUrl"] = str(output_file)
                book["isAudioGenerated"] = True
                continue

            logger.info(f"[{i+1}/{len(books)}] 🎙️ 生成: 《{title}》")

            # 使用 edge-tts 生成音频
            cmd = [
                "npx", "edge-tts",
                "--text", book["script"],
                "--voice", "zh-CN-YunxiNeural",
                "--write-media", str(output_file),
                "--rate", "-10%",
                "--pitch", "-5Hz"
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

            if result.returncode == 0:
                book["audioUrl"] = str(output_file)
                book["isAudioGenerated"] = True
                logger.info(f"  ✅ 音频生成成功")
            else:
                logger.error(f"  ❌ 音频生成失败: {result.stderr[:200]}")
                book["isAudioGenerated"] = False

    except FileNotFoundError:
        logger.warning("⚠️ edge-tts 未安装，跳过音频生成")
        logger.info("   安装方法: npm install -g edge-tts")
    except Exception as e:
        logger.error(f"❌ 音频生成异常: {e}")

    # 保存结果
    output = DATA_DIR / "step3_books_with_audio.json"
    with open(output, 'w', encoding='utf-8') as f:
        json.dump(books, f, ensure_ascii=False, indent=2)

    return books


# ==================== 步骤4：准备数据库格式 ====================
def step4_prepare_for_database(books: List[Dict]) -> List[Dict]:
    """转换为云数据库导入格式"""
    logger.info(f"\n{'═'*60}")
    logger.info(f"💾 步骤4：准备数据库导入格式")
    logger.info(f"{'═'*60}")

    now = int(time.time() * 1000)
    db_books = []

    for i, book in enumerate(books):
        db_book = {
            # 基础信息
            "title": book.get("title", ""),
            "author": book.get("author", "未知作者"),
            "category": book.get("category", 12),
            "categoryName": book.get("categoryName", "其他"),
            "publisher": book.get("publisher", ""),
            "isbn": book.get("isbn", ""),
            "publishDate": book.get("publishDate", ""),
            "pages": book.get("pages", 0),
            "description": book.get("description", ""),
            "coverColor": book.get("coverColor", "#FFE4C4"),
            "coverUrl": book.get("coverUrl", ""),

            # 字幕/文稿
            "script": book.get("script", ""),
            "scriptLength": book.get("scriptLength", 0),
            "scriptSource": book.get("scriptSource", ""),
            "scriptVersion": book.get("scriptVersion", 1),
            "sentences": book.get("sentences", []),

            # 音频信息
            "audioUrl": book.get("audioUrl", ""),
            "audioDuration": book.get("audioDuration", 0),
            "audioDurationText": book.get("audioDurationText", ""),
            "isAudioGenerated": book.get("isAudioGenerated", False),
            "ttsVoice": book.get("ttsVoice", "zh-CN-YunxiNeural"),
            "ttsRate": book.get("ttsRate", "-10%"),
            "ttsPitch": book.get("ttsPitch", "-5Hz"),

            # 状态标记
            "isHot": book.get("isHot", i < 3),  # 前3本标记为热门
            "isGenerated": book.get("isGenerated", False),
            "isPublished": book.get("isPublished", False),
            "viewCount": book.get("viewCount", 0),
            "playCount": book.get("playCount", 0),

            # 质量管理
            "qualityScore": book.get("qualityScore", 0),
            "qualityNote": book.get("qualityNote", ""),

            # 时间戳
            "createTime": book.get("createTime", now),
            "updateTime": now,

            # 来源追溯
            "source": book.get("source", "manual"),
            "sourceUrl": book.get("sourceUrl", ""),
            "crawlTime": book.get("crawlTime", now),
            "importedBooks": f"batch_{datetime.now().strftime('%Y%m%d_%H%M')}"
        }
        db_books.append(db_book)

    # 保存
    output = DATA_DIR / "step4_for_database_import.json"
    with open(output, 'w', encoding='utf-8') as f:
        json.dump(db_books, f, ensure_ascii=False, indent=2)

    # 预览
    logger.info(f"\n📊 数据预览 ({len(db_books)} 本书):")
    for b in db_books[:5]:
        logger.info(f"  📖 《{b['title']}》- {b['author']} [{b['categoryName']}]")
        logger.info(f"     字幕: {b['scriptLength']}字 | 热门: {'是' if b['isHot'] else '否'} | 已生成: {'是' if b['isGenerated'] else '否'}")

    logger.info(f"\n💾 数据库格式已保存: {output}")
    return db_books


# ==================== 步骤5：导入云数据库 ====================
def step5_import_to_cloud(books: List[Dict]) -> Dict:
    """导入到微信云开发数据库"""
    logger.info(f"\n{'═'*60}")
    logger.info(f"☁️ 步骤5：导入云数据库")
    logger.info(f"{'═'*60}")

    app_id = os.getenv("WECHAT_APP_ID", "")
    secret = os.getenv("WECHAT_SECRET", "")
    env_id = os.getenv("WECHAT_ENV_ID", "cloud1-d2ggs9k1bf3aa2a18")

    if not app_id or not secret:
        logger.warning("⚠️ 未配置微信 AppID/Secret")
        logger.info("   请在 pipeline/.env 中设置:")
        logger.info("   WECHAT_APP_ID=你的AppID")
        logger.info("   WECHAT_SECRET=你的Secret")
        logger.info("\n📋 你可以手动导入数据:")
        logger.info(f"   1. 打开微信开发者工具 → 云开发控制台")
        logger.info(f"   2. 选择数据库 → books 集合")
        logger.info(f"   3. 点击导入，选择: {DATA_DIR / 'step4_for_database_import.json'}")
        return {"success": False, "error": "未配置微信云开发参数"}

    try:
        from modules.cloud_import import WeChatCloudImporter

        importer = WeChatCloudImporter(app_id=app_id, secret=secret, env_id=env_id)

        # 获取 access_token
        if not importer.get_access_token():
            logger.error("❌ 获取 access_token 失败")
            return {"success": False, "error": "获取access_token失败"}

        # 批量导入
        result = importer.batch_import(books)

        if result and result.get("success"):
            data = result.get("data", {})
            imported = data.get("imported", 0)
            skipped = data.get("skipped", 0)
            failed = data.get("failed", 0)

            logger.info(f"\n🎉 导入完成！")
            logger.info(f"   ✅ 新增: {imported} 条")
            logger.info(f"   ⏭️  跳过: {skipped} 条（已存在）")
            if failed > 0:
                logger.info(f"   ❌ 失败: {failed} 条")
        else:
            logger.error(f"❌ 导入失败: {result.get('error', '未知错误')}")

        return result

    except ImportError:
        logger.error("❌ 无法导入 cloud_import 模块")
        return {"success": False, "error": "模块导入失败"}
    except Exception as e:
        logger.error(f"❌ 导入异常: {e}")
        return {"success": False, "error": str(e)}


# ==================== 生成金句数据 ====================
def generate_quotes_collection(books: List[Dict]) -> List[Dict]:
    """
    从书籍数据中提取金句，生成 quotes 集合数据
    """
    logger.info(f"\n{'═'*60}")
    logger.info(f"💬 生成金句集合数据")
    logger.info(f"{'═'*60}")

    quotes = []
    now = int(time.time() * 1000)

    for book in books:
        title = book.get("title", "")
        author = book.get("author", "")
        category_name = book.get("categoryName", "其他")
        quotes_text = book.get("quotes", "")

        if not quotes_text:
            continue

        # 解析金句
        import re
        for line in quotes_text.split('\n'):
            line = line.strip()
            if not line:
                continue

            q_match = re.match(r'["""](.+?)["""]\s*(?:——|—)\s*(.+)', line)
            if q_match:
                quotes.append({
                    "content": q_match.group(1),
                    "author": author,
                    "bookName": title,
                    "categoryName": category_name,
                    "playCount": 0,
                    "likeCount": 0,
                    "createTime": now,
                    "updateTime": now
                })

    # 保存金句数据
    if quotes:
        output = DATA_DIR / "quotes_for_database_import.json"
        with open(output, 'w', encoding='utf-8') as f:
            json.dump(quotes, f, ensure_ascii=False, indent=2)
        logger.info(f"✅ 生成 {len(quotes)} 条金句数据")
        logger.info(f"💾 保存到: {output}")
    else:
        logger.warning("⚠️ 未提取到任何金句")

    return quotes


# ==================== 主流程 ====================
def main():
    parser = argparse.ArgumentParser(
        description="听书小程序 - 一站式数据导入工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python run_pipeline.py                               # 完整流程
  python run_pipeline.py --source douban --api minimax # 豆瓣+MiniMax
  python run_pipeline.py --skip-crawl                 # 跳过爬取
  python run_pipeline.py --dry-run                     # 预览模式
  python run_pipeline.py --books "小王子,活着"          # 指定书籍
        """
    )
    parser.add_argument("--source", choices=["auto", "douban", "aliyun", "manual"], default="manual",
                        help="爬取数据源 (默认: manual)")
    parser.add_argument("--api", choices=["minimax", "doubao"], default="minimax",
                        help="字幕生成API (默认: minimax)")
    parser.add_argument("--skip-crawl", action="store_true", help="跳过爬取步骤")
    parser.add_argument("--skip-script", action="store_true", help="跳过字幕生成")
    parser.add_argument("--skip-audio", action="store_true", help="跳过音频生成")
    parser.add_argument("--skip-import", action="store_true", help="跳过云数据库导入")
    parser.add_argument("--books", type=str, help="指定书名，逗号分隔")
    parser.add_argument("--file", type=str, help="从文件读取书名列表")
    parser.add_argument("--input", type=str, help="已有数据JSON文件（跳过爬取直接用）")
    parser.add_argument("--dry-run", action="store_true", help="预览模式（模拟文稿，不调用API）")
    args = parser.parse_args()

    # 加载环境变量
    load_env()

    print(f"""
╔══════════════════════════════════════════════════════════╗
║                                                          ║
║         📚 听书小程序 - 一站式数据导入工具 v2.0            ║
║                                                          ║
║         爬取书籍 → 生成字幕 → 导入云数据库                  ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝
    """)

    start_time = time.time()

    # ==================== 步骤1：爬取 ====================
    if args.skip_crawl and not args.input:
        # 尝试加载已有数据
        default_input = DATA_DIR / "crawled_output.json"
        if default_input.exists():
            with open(default_input, 'r', encoding='utf-8') as f:
                books = json.load(f)
            logger.info(f"📂 加载已有爬取数据: {default_input} ({len(books)} 本书)")
        else:
            logger.error("❌ 无已有爬取数据，请先运行爬取步骤")
            sys.exit(1)
    elif args.input:
        input_path = Path(args.input)
        if not input_path.is_absolute():
            input_path = DATA_DIR / args.input
        with open(input_path, 'r', encoding='utf-8') as f:
            books = json.load(f)
        logger.info(f"📂 加载输入数据: {input_path} ({len(books)} 本书)")
    else:
        # 确定书名列表
        if args.books:
            book_names = [b.strip() for b in args.books.split(",")]
        elif args.file:
            with open(args.file, 'r', encoding='utf-8') as f:
                book_names = [line.strip() for line in f if line.strip() and not line.startswith("#")]
        else:
            from crawl_books import DEFAULT_BOOKS
            book_names = DEFAULT_BOOKS

        books = step1_crawl(book_names, source=args.source)

    # ==================== 步骤2：生成字幕 ====================
    if not args.skip_script:
        books = step2_generate_scripts(books, api=args.api, dry_run=args.dry_run)
    else:
        logger.info("\n⏭️ 跳过字幕生成步骤")

    # ==================== 步骤3：生成音频 ====================
    if not args.skip_audio:
        books = step3_generate_audio(books)
    else:
        logger.info("\n⏭️ 跳过音频生成步骤")

    # ==================== 步骤4：准备数据库格式 ====================
    db_books = step4_prepare_for_database(books)

    # ==================== 生成金句数据 ====================
    quotes = generate_quotes_collection(db_books)

    # ==================== 步骤5：导入云数据库 ====================
    if not args.skip_import:
        result = step5_import_to_cloud(db_books)
    else:
        logger.info("\n⏭️ 跳过云数据库导入")
        logger.info(f"\n📋 手动导入步骤:")
        logger.info(f"   1. 打开微信开发者工具 → 云开发控制台")
        logger.info(f"   2. 创建 books 和 quotes 集合（如果不存在）")
        logger.info(f"   3. 选择 books 集合 → 导入 → 选择:")
        logger.info(f"      {DATA_DIR / 'step4_for_database_import.json'}")
        logger.info(f"   4. 选择 quotes 集合 → 导入 → 选择:")
        logger.info(f"      {DATA_DIR / 'quotes_for_database_import.json'}")

    # ==================== 完成 ====================
    elapsed = time.time() - start_time
    print(f"\n{'═'*60}")
    print(f"🎉 全部流程完成！耗时: {elapsed:.1f}秒")
    print(f"{'═'*60}")
    print(f"\n📊 处理结果:")
    print(f"   📚 书籍: {len(db_books)} 本")
    print(f"   💬 金句: {len(quotes)} 条")
    print(f"   📁 数据目录: {DATA_DIR}")
    print(f"\n📂 生成的文件:")
    print(f"   📄 爬取数据: data_source/crawled_output.json")
    print(f"   📄 文稿数据: data_source/step2_books_with_script.json")
    print(f"   📄 导入数据: data_source/step4_for_database_import.json")
    print(f"   📄 金句数据: data_source/quotes_for_database_import.json")
    print(f"   📁 文稿文件: data_source/scripts/")
    print(f"\n💡 下一步:")
    print(f"   1. 在微信开发者工具中部署云函数")
    print(f"   2. 在云开发控制台导入数据（或配置WECHAT_APP_ID/SECRET后自动导入）")
    print(f"   3. 安装edge-tts后运行音频生成: npm install -g edge-tts")


if __name__ == "__main__":
    main()
