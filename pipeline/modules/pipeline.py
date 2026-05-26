"""
流水线调度模块
串联所有处理环节，支持并发和断点续传
"""
import os
import time
import logging
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

# 导入各模块
from modules.config_loader import get_config
from modules.book_info import BookInfoFetcher
from modules.content_gen import ContentGenerator
from modules.tts_synth import TTSEngine
from modules.data_storage import DataStorage


class Pipeline:
    def __init__(self):
        self.config = get_config()
        self._setup_logging()

        # 初始化各模块
        self.book_fetcher = BookInfoFetcher(self.config)
        self.content_gen = ContentGenerator(self.config)
        self.tts_engine = TTSEngine(self.config)

        # 输出目录（pipeline根目录）
        base_dir = Path(__file__).parent.parent
        self.output_dir = base_dir / "output"
        self.storage = DataStorage(self.output_dir)

        # 流水线配置
        self.max_workers = self.config.pipeline.get("max_workers", 5)
        self.retry_times = self.config.pipeline.get("retry_times", 3)
        self.batch_size = self.config.pipeline.get("batch_size", 10)

        # 统计
        self.stats = {
            "total": 0,
            "success": 0,
            "failed": 0,
            "skipped": 0,
        }

    def _setup_logging(self):
        """配置日志"""
        log_dir = Path(__file__).parent / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        log_file = log_dir / f"pipeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(message)s",
            handlers=[
                logging.FileHandler(log_file, encoding="utf-8"),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

    def run(self, book_list=None):
        """
        运行流水线
        book_list: 书名列表，None则从文件读取
        """
        # 获取书名列表
        if book_list is None:
            book_list = self._load_book_list()

        # 断点续传：过滤已处理的书籍
        processed = self.storage.get_processed_books()
        if processed:
            original_count = len(book_list)
            book_list = [b for b in book_list if b not in processed]
            self.stats["skipped"] = original_count - len(book_list)
            print(f"\n断点续传：跳过 {self.stats['skipped']} 本已处理的书籍")

        if not book_list:
            print("所有书籍已处理完成！")
            return

        self.stats["total"] = len(book_list)
        print(f"\n{'='*50}")
        print(f"开始处理 {len(book_list)} 本书籍")
        print(f"并发数: {self.max_workers}")
        print(f"输出目录: {self.output_dir}")
        print(f"{'='*50}\n")

        # 批量处理
        start_time = time.time()

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {}
            for book_name in book_list:
                future = executor.submit(self._process_single_book, book_name)
                futures[future] = book_name

            results = []
            for future in as_completed(futures):
                book_name = futures[future]
                try:
                    result = future.result()
                    results.append(result)
                    if result.get("status") == "completed":
                        self.stats["success"] += 1
                    else:
                        self.stats["failed"] += 1
                except Exception as e:
                    print(f"处理异常: {book_name} - {e}")
                    self.stats["failed"] += 1
                    results.append({"book_name": book_name, "status": "failed", "error": str(e)})

        # 保存批次索引
        self.storage.save_batch_index(results)

        # 打印统计
        elapsed = time.time() - start_time
        self._print_stats(elapsed)

    def _process_single_book(self, book_name):
        """
        处理单本书
        流程：图书数据 → AI文稿 → TTS音频 → 数据存储
        """
        print(f"\n>>> 开始处理：{book_name}")

        result = {
            "book_name": book_name,
            "status": "failed",
            "error": None
        }

        try:
            # 步骤1：获取图书基础数据
            book_info = self.book_fetcher.fetch(book_name, self.output_dir)
            if not book_info:
                raise Exception("获取图书数据失败")

            # 步骤2：生成AI解读文稿+金句
            content = self.content_gen.generate(book_info)
            book_info["script"] = content.get("script", "")
            book_info["quotes"] = content.get("quotes", [])

            # 步骤3：TTS音频合成
            audio_path = self.output_dir / "audios" / f"{book_name}.wav"
            audio_result = self.tts_engine.synthesize(
                book_info["script"],
                str(audio_path),
                book_name
            )
            book_info["audio_path"] = audio_result

            # 步骤4：保存数据包
            json_path = self.storage.save_book_package(book_info, book_name)
            book_info["json_path"] = json_path

            result = {
                "book_name": book_name,
                "book_id": Path(json_path).stem,
                "author": book_info.get("author"),
                "script_length": len(book_info.get("script", "")),
                "quotes_count": len(book_info.get("quotes", [])),
                "audio_path": audio_result,
                "status": "completed" if audio_result else "script_only",
            }

            print(f"<<< 完成：{book_name}")

        except Exception as e:
            print(f"<<< 失败：{book_name} - {e}")
            result["error"] = str(e)

        return result

    def _load_book_list(self):
        """加载书名列表"""
        # 测试模式：只取前3本
        if self.config.is_test_mode():
            print("测试模式：使用配置中的测试书名")
            return self.config.test_books[:3]

        # 从文件读取
        book_file = Path(__file__).parent / "book_list.txt"
        if book_file.exists():
            with open(book_file, "r", encoding="utf-8") as f:
                books = [line.strip() for line in f if line.strip()]
            return books

        # 默认测试书名
        return self.config.test_books[:3]

    def _print_stats(self, elapsed):
        """打印处理统计"""
        print(f"\n{'='*50}")
        print(f"处理完成！耗时: {elapsed:.1f}秒")
        print(f"总计: {self.stats['total']} 本")
        print(f"成功: {self.stats['success']} 本")
        print(f"失败: {self.stats['failed']} 本")
        if self.stats['skipped']:
            print(f"跳过: {self.stats['skipped']} 本（已处理）")
        print(f"平均: {elapsed/max(self.stats['total'],1):.1f}秒/本")
        print(f"{'='*50}")
        print(f"输出目录: {self.output_dir / 'data'}")
