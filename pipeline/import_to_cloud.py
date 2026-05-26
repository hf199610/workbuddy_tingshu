#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MiniMax 文稿生成 + 微信云数据库导入流水线

功能：
1. 读取 JSON 数据文件（固定5条）
2. 使用 MiniMax 循环生成/更新字幕文稿
3. 调用云函数导入到数据库（自动去重）
"""
import os
import sys
import json
import time
import logging
from pathlib import Path
from datetime import datetime

# 添加 modules 到路径
sys.path.insert(0, str(Path(__file__).parent))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)


def load_config():
    """加载配置"""
    # 尝试加载 .env 文件
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        with open(env_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ.setdefault(key.strip(), value.strip())

    # 尝试从 miniprogram/.env 加载
    mp_env_file = Path(__file__).parent.parent / "miniprogram" / ".env"
    if mp_env_file.exists():
        with open(mp_env_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ.setdefault(key.strip(), value.strip())

    return {
        "minimax_api_key": os.getenv("ANTHROPIC_API_KEY"),
        "minimax_base_url": os.getenv("ANTHROPIC_BASE_URL"),
        "wechat_env_id": os.getenv("WECHAT_ENV_ID", "cloud1-d2ggs9k1bf3aa2a18"),
        "wechat_app_id": os.getenv("WECHAT_APP_ID"),
        "wechat_secret": os.getenv("WECHAT_SECRET"),
        "import_limit": 5,  # 固定导入5条
        "data_file": os.getenv("IMPORT_DATA_FILE", "step4_for_database_import.json")
    }


def load_source_data(data_file: Path) -> list:
    """加载源数据"""
    with open(data_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_updated_data(data_file: Path, data: list):
    """保存更新后的数据"""
    with open(data_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def process_books(config: dict, books: list, minimax_client=None) -> list:
    """
    处理书籍列表

    Args:
        config: 配置
        books: 书籍列表
        minimax_client: MiniMax 客户端

    Returns:
        list: 处理后的书籍列表
    """
    processed = []
    limit = config["import_limit"]

    for i, book in enumerate(books[:limit]):
        title = book.get("title", "未知")
        author = book.get("author", "未知")
        description = book.get("description", "")

        print(f"\n┌─ [{i+1}/{min(limit, len(books))}] 处理: {title}")
        print(f"│  作者: {author}")

        # 检查是否已有文稿
        if book.get("script") and book.get("isGenerated"):
            print(f"│  ⏭️  已有文稿，跳过生成")
            processed.append(book)
            processed_books_count = len([b for b in processed if b.get("isGenerated")])
            print(f"│  📊 已处理: {processed_books_count} 条")
            print(f"└")
            continue

        # 调用 MiniMax 生成文稿
        if minimax_client:
            print(f"│  📝 正在调用 MiniMax 生成文稿...")
            try:
                script = minimax_client.generate_script(title, author, description)
                sentences = minimax_client.split_sentences(script)

                book["script"] = script
                book["scriptLength"] = len(script)
                book["sentences"] = sentences
                book["isGenerated"] = True
                book["updateTime"] = int(datetime.now().timestamp() * 1000)

                print(f"│  ✅ 文稿生成完成 ({len(script)} 字, {len(sentences)} 句)")
            except Exception as e:
                print(f"│  ❌ 文稿生成失败: {e}")
                continue
        else:
            print(f"│  ⚠️  未配置 MiniMax，跳过生成")
            continue

        processed.append(book)

        processed_books_count = len([b for b in processed if b.get("script")])
        print(f"│  📊 已处理: {processed_books_count} 条")
        print(f"└")

        # 避免请求过快
        time.sleep(0.5)

    return processed


def import_to_cloud(config: dict, books: list) -> dict:
    """
    导入书籍到云数据库

    Args:
        config: 配置
        books: 书籍列表

    Returns:
        dict: 导入结果
    """
    try:
        from modules.cloud_import import WeChatCloudImporter
    except ImportError:
        logger.error("无法导入 cloud_import 模块")
        return {"success": False, "error": "模块导入失败"}

    importer = WeChatCloudImporter(
        app_id=config.get("wechat_app_id"),
        secret=config.get("wechat_secret"),
        env_id=config.get("wechat_env_id")
    )

    # 获取 access_token
    if not importer.get_access_token():
        logger.error("无法获取 access_token，请检查 AppID 和 Secret 配置")
        return {"success": False, "error": "无法获取 access_token"}

    # 调用云函数批量导入
    result = importer.batch_import(books)

    return result


def main():
    print("""
╔══════════════════════════════════════════════════════════╗
║                                                          ║
║         📚 听书小程序 - 数据导入工具 v1.0                  ║
║                                                          ║
║         数据源 → MiniMax生成文稿 → 云数据库导入            ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝
    """)

    # 加载配置
    config = load_config()

    # 检查 MiniMax 配置
    minimax_client = None
    if config.get("minimax_api_key"):
        try:
            from modules.minimax_client import MiniMaxClient
            minimax_client = MiniMaxClient(
                api_key=config["minimax_api_key"],
                base_url=config.get("minimax_base_url")
            )
            logger.info("✅ MiniMax 客户端初始化成功")
        except Exception as e:
            logger.error(f"❌ MiniMax 客户端初始化失败: {e}")
    else:
        logger.warning("⚠️  未配置 MiniMax API 密钥，跳过文稿生成")

    # 数据源路径
    data_file = Path(__file__).parent / "data_source" / config["data_file"]

    # 如果数据文件不在 pipeline/data_source，就检查上一级
    if not data_file.exists():
        data_file = Path(__file__).parent.parent / "data_source" / config["data_file"]

    if not data_file.exists():
        print(f"\n❌ 数据文件不存在: {data_file}")
        print(f"   请确保文件存在于: {data_file}")
        sys.exit(1)

    print(f"\n📂 数据源: {data_file}")
    print(f"📖 导入限制: {config['import_limit']} 条\n")

    # 步骤1: 加载数据
    print("=" * 55)
    print("📥 步骤1: 读取数据")
    print("=" * 55)
    books = load_source_data(data_file)
    print(f"✅ 读取到 {len(books)} 条书籍数据")

    if len(books) > config["import_limit"]:
        print(f"ℹ️  将处理前 {config['import_limit']} 条数据")

    # 步骤2: MiniMax 文稿生成
    if minimax_client:
        print("\n" + "=" * 55)
        print("🤖 步骤2: MiniMax 文稿生成")
        print("=" * 55)
        processed_books = process_books(config, books, minimax_client)

        # 保存更新后的数据
        save_updated_data(data_file, books)
        print(f"\n✅ 数据已保存到: {data_file}")
    else:
        processed_books = [b for b in books[:config["import_limit"]] if b.get("script")]
        print(f"\n⚠️  跳过 MiniMax 生成，待导入 {len(processed_books)} 条已有文稿的数据")

    if not processed_books:
        print("\n❌ 没有可导入的数据（无文稿或生成失败）")
        sys.exit(1)

    # 步骤3: 云数据库导入
    print("\n" + "=" * 55)
    print("☁️  步骤3: 导入云数据库")
    print("=" * 55)

    if config.get("wechat_app_id") and config.get("wechat_secret"):
        result = import_to_cloud(config, processed_books)

        print("\n" + "=" * 55)
        print("📊 导入结果")
        print("=" * 55)

        if result and result.get("success"):
            data = result.get("data", {})
            imported = data.get("imported", 0)
            skipped = data.get("skipped", 0)
            failed = data.get("failed", 0)

            print(f"\n🎉 导入完成！")
            print(f"   ✅ 新增导入: {imported} 条")
            print(f"   ⏭️  重复跳过: {skipped} 条")

            if skipped > 0 and data.get("skippedBooks"):
                print(f"   📋 跳过书籍: {', '.join(data['skippedBooks'][:5])}")

            if failed > 0:
                print(f"   ❌ 导入失败: {failed} 条")
                errors = data.get("errors", [])
                for err in errors[:3]:
                    print(f"      - {err.get('title', '未知')}: {err.get('error', '未知错误')}")
        else:
            print(f"\n❌ 导入失败: {result.get('error', '未知错误')}")
            print(f"   提示: 请确保云函数 batchImportBooks 已上传并配置正确")
    else:
        print("\n⚠️  未配置微信云开发参数，跳过导入")
        print(f"   请设置 WECHAT_APP_ID 和 WECHAT_SECRET 环境变量")

    print("\n" + "=" * 55)
    print("✨ 完成!")
    print("=" * 55)

    # 关闭 MiniMax 客户端
    if minimax_client:
        minimax_client.close()


if __name__ == "__main__":
    main()
