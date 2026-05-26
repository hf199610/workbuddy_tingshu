"""
图书数据获取模块
使用阿里云图书API获取书籍基础信息（封面/作者/简介/ISBN）
"""
import os
import requests
import time
from pathlib import Path

class BookInfoFetcher:
    def __init__(self, config):
        self.app_code = config.aliyun.get("app_code")
        self.base_url = config.aliyun.get("base_url")

    def fetch(self, book_name, output_dir=None):
        """
        获取单本书的基础信息
        返回: dict 包含 name, author, publisher, isbn, intro, cover_path
        """
        print(f"  [图书数据] 正在获取《{book_name}》...")

        # 如果是测试APPCODE或未配置，返回模拟数据
        if not self.app_code or self.app_code == "你的阿里云APPCODE":
            print(f"  [图书数据] 使用模拟数据")
            return self._mock_book_info(book_name)

        try:
            url = f"{self.base_url}/book/info"
            headers = {
                "Authorization": f"APPCODE {self.app_code}",
                "Content-Type": "application/json"
            }
            params = {"name": book_name}

            response = requests.get(url, headers=headers, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                result = {
                    "name": data.get("bookName", book_name),
                    "author": data.get("author", "未知"),
                    "publisher": data.get("publisher", "未知"),
                    "isbn": data.get("isbn", ""),
                    "intro": data.get("intro", ""),
                    "publish_date": data.get("publishDate", ""),
                }

                # 下载封面图
                if data.get("cover") and output_dir:
                    cover_url = data["cover"]
                    cover_path = self._download_cover(cover_url, book_name, output_dir)
                    result["cover_path"] = cover_path

                print(f"  [图书数据] 获取成功：{result['author']} | {result['publisher']}")
                return result
            else:
                print(f"  [图书数据] API返回错误: {response.status_code}")
                return self._mock_book_info(book_name)

        except Exception as e:
            print(f"  [图书数据] 获取失败: {e}，使用模拟数据")
            return self._mock_book_info(book_name)

    def _download_cover(self, cover_url, book_name, output_dir):
        """下载封面图"""
        try:
            covers_dir = Path(output_dir) / "covers"
            covers_dir.mkdir(parents=True, exist_ok=True)

            safe_name = self._sanitize_filename(book_name)
            cover_path = covers_dir / f"{safe_name}.jpg"

            response = requests.get(cover_url, timeout=15)
            if response.status_code == 200:
                with open(cover_path, "wb") as f:
                    f.write(response.content)
                return str(cover_path)
        except Exception as e:
            print(f"  [图书数据] 封面下载失败: {e}")
        return None

    def _mock_book_info(self, book_name):
        """模拟图书数据（测试用）"""
        base = {
            "name": book_name,
            "author": "未知作者",
            "publisher": "未知出版社",
            "isbn": "",
            "intro": f"这是《{book_name}》的简介，暂无详细信息。",
            "publish_date": ""
        }
        mock_data = {
            "活着": {
                "name": "活着",
                "author": "余华",
                "publisher": "作家出版社",
                "isbn": "9787506365437",
                "intro": "《活着》讲述了农村人福贵悲惨的人生遭遇。福贵本是个阔少爷，可他嗜赌如命，终于赌光了家业，一贫如洗。他的父亲被他活活气死，母亲则在穷困中患了重病。",
                "publish_date": "2012-08-01"
            },
            "平凡的世界": {
                "name": "平凡的世界",
                "author": "路遥",
                "publisher": "人民文学出版社",
                "isbn": "9787020049329",
                "intro": "《平凡的世界》是中国作家路遥创作的一部全景式地表现中国当代城乡社会生活的百万字长篇小说。全书共三部。",
                "publish_date": "2005-05-01"
            },
            "百年孤独": {
                "name": "百年孤独",
                "author": "加西亚·马尔克斯",
                "publisher": "南海出版公司",
                "isbn": "9787544253994",
                "intro": "《百年孤独》是魔幻现实主义文学的代表作，描写了布恩迪亚家族七代人的传奇故事，以及加勒比海沿岸小镇马孔多的百年兴衰。",
                "publish_date": "2011-06-01"
            }
        }
        return mock_data.get(book_name, base)

    @staticmethod
    def _sanitize_filename(name):
        """清理文件名"""
        for char in ['\\', '/', ':', '*', '?', '"', '<', '>', '|']:
            name = name.replace(char, '_')
        return name
