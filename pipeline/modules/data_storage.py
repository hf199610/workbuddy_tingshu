"""
数据存储模块
将处理完成的书籍数据包保存为JSON文件
"""
import os
import json
from pathlib import Path
from datetime import datetime


class DataStorage:
    def __init__(self, output_dir):
        self.output_dir = Path(output_dir)
        self.data_dir = self.output_dir / "data"
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def save_book_package(self, book_data, book_name):
        """
        保存单本书的完整数据包
        book_data: dict 包含 book_info, script, quotes, audio_path 等
        """
        # 生成唯一ID
        book_id = self._generate_book_id(book_name)

        # 打包数据
        package = {
            "book_id": book_id,
            "book_name": book_name,
            "author": book_data.get("author", ""),
            "publisher": book_data.get("publisher", ""),
            "isbn": book_data.get("isbn", ""),
            "intro": book_data.get("intro", ""),
            "publish_date": book_data.get("publish_date", ""),
            "cover_path": book_data.get("cover_path", ""),
            "script": book_data.get("script", ""),
            "script_length": len(book_data.get("script", "")),
            "estimated_duration": self._estimate_duration(book_data.get("script", "")),
            "quotes": book_data.get("quotes", []),
            "quotes_count": len(book_data.get("quotes", [])),
            "audio_path": book_data.get("audio_path", ""),
            "status": "completed" if book_data.get("audio_path") else "script_only",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        # 保存JSON文件
        json_path = self.data_dir / f"{book_id}.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(package, f, ensure_ascii=False, indent=2)

        print(f"  [数据存储] 已保存: {json_path.name}")
        return str(json_path)

    def _generate_book_id(self, book_name):
        """生成书籍唯一ID（简化版：用名称拼音首字母+时间戳）"""
        # 简单哈希
        import hashlib
        hash_str = hashlib.md5(book_name.encode()).hexdigest()[:8]
        return f"book_{hash_str}"

    def _estimate_duration(self, script):
        """估算音频时长（按350字/分钟计算）"""
        char_count = len(script)
        minutes = char_count / 350
        return round(minutes, 1)

    def save_batch_index(self, book_list):
        """保存批次索引文件"""
        index_path = self.data_dir / "batch_index.json"
        index = {
            "total_books": len(book_list),
            "completed": sum(1 for b in book_list if b.get("status") == "completed"),
            "script_only": sum(1 for b in book_list if b.get("status") == "script_only"),
            "failed": sum(1 for b in book_list if b.get("status") == "failed"),
            "books": book_list,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(index, f, ensure_ascii=False, indent=2)
        print(f"  [数据存储] 批次索引已更新: {index_path.name}")

    def get_processed_books(self):
        """获取已处理的书籍列表（用于断点续传）"""
        processed = []
        for json_file in self.data_dir.glob("*.json"):
            if json_file.name == "batch_index.json":
                continue
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    processed.append(data.get("book_name"))
            except:
                pass
        return processed
