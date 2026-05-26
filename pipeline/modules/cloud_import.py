"""
微信云数据库导入模块
支持去重检查和批量导入
"""
import os
import json
import logging
from typing import List, Dict, Tuple, Optional

logger = logging.getLogger(__name__)


class WeChatCloudImporter:
    """微信云数据库导入器"""

    def __init__(self, app_id: Optional[str] = None, secret: Optional[str] = None,
                 env_id: Optional[str] = None):
        """
        初始化云数据库导入器

        Args:
            app_id: 微信小程序 AppID，默认从环境变量读取
            secret: 微信小程序 Secret，默认从环境变量读取
            env_id: 云开发环境 ID，默认从环境变量读取
        """
        self.app_id = app_id or os.getenv("WECHAT_APP_ID")
        self.secret = secret or os.getenv("WECHAT_SECRET")
        self.env_id = env_id or os.getenv("WECHAT_ENV_ID", "cloud1-d2ggs9k1bf3aa2a18")
        self.access_token = None

        if not self.app_id or not self.secret:
            logger.warning("未配置微信 AppID/Secret，无法获取 access_token")

    def get_access_token(self) -> Optional[str]:
        """
        获取 access_token

        Returns:
            str: access_token 或 None
        """
        import httpx

        if not self.app_id or not self.secret:
            logger.error("缺少 AppID 或 Secret")
            return None

        url = "https://api.weixin.qq.com/cgi-bin/token"
        params = {
            "grant_type": "client_credential",
            "appid": self.app_id,
            "secret": self.secret
        }

        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.get(url, params=params)
                result = response.json()

                if "access_token" in result:
                    self.access_token = result["access_token"]
                    logger.info("获取 access_token 成功")
                    return self.access_token
                else:
                    logger.error(f"获取 access_token 失败: {result}")
                    return None
        except Exception as e:
            logger.error(f"获取 access_token 异常: {e}")
            return None

    def check_exists(self, title: str, author: str) -> bool:
        """
        检查书籍是否已存在于云数据库

        Args:
            title: 书名
            author: 作者

        Returns:
            bool: 是否已存在
        """
        import httpx

        if not self.access_token:
            if not self.get_access_token():
                return False

        url = "https://api.weixin.qq.com/tcb/databasequery"
        params = {"access_token": self.access_token}

        # 使用聚合查询检查是否存在
        query = f"""
db.collection('books').where({{
    'title': '{title}',
    'author': '{author}'
}}).limit(1).get()
"""

        data = {
            "env": self.env_id,
            "query": query
        }

        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(url, params=params, json=data)
                result = response.json()

                if result.get("errcode") == 0:
                    data_list = result.get("data", [])
                    if data_list and len(data_list) > 0:
                        logger.info(f"[去重] 跳过已存在: {title} - {author}")
                        return True
                else:
                    logger.warning(f"查询失败: {result}")

                return False
        except Exception as e:
            logger.error(f"检查重复异常: {e}")
            return False

    def check_exists_batch(self, books: List[Dict]) -> Dict[str, bool]:
        """
        批量检查书籍是否已存在

        Args:
            books: 书籍列表

        Returns:
            Dict[str, bool]: key 为 "title-author"，value 为是否已存在
        """
        results = {}
        for book in books:
            key = f"{book.get('title', '')}-{book.get('author', '')}"
            results[key] = self.check_exists(book.get('title', ''), book.get('author', ''))
        return results

    def call_cloud_function(self, function_name: str, data: Dict) -> Dict:
        """
        调用云函数

        Args:
            function_name: 云函数名称
            data: 传递给云函数的数据

        Returns:
            Dict: 云函数返回结果
        """
        import httpx

        if not self.access_token:
            if not self.get_access_token():
                return {"success": False, "error": "无法获取 access_token"}

        url = "https://api.weixin.qq.com/tcb/invokecloudfunction"
        params = {
            "access_token": self.access_token,
            "env": self.env_id,
            "name": function_name
        }

        payload = {
            **data
        }

        try:
            with httpx.Client(timeout=60.0) as client:
                response = client.post(url, params=params, json=payload)
                result = response.json()

                # 解析云函数返回
                if result.get("resp_data"):
                    try:
                        return json.loads(result["resp_data"])
                    except json.JSONDecodeError:
                        return {"success": False, "error": result["resp_data"]}

                return result
        except Exception as e:
            logger.error(f"调用云函数异常: {e}")
            return {"success": False, "error": str(e)}

    def batch_import(self, books: List[Dict]) -> Dict:
        """
        批量导入书籍（调用云函数）

        Args:
            books: 书籍列表

        Returns:
            Dict: 导入结果统计
        """
        logger.info(f"开始批量导入 {len(books)} 条数据...")

        result = self.call_cloud_function("batchImportBooks", {
            "action": "import",
            "data": books
        })

        return result

    def batch_import_with_local_dedup(self, books: List[Dict]) -> Tuple[int, int, int, List[Dict]]:
        """
        批量导入书籍（本地去重检查）

        Args:
            books: 书籍列表

        Returns:
            Tuple[int, int, int, List[Dict]]: (成功数, 跳过数, 失败数, 错误列表)
        """
        import time

        success_count = 0
        skip_count = 0
        error_count = 0
        errors = []
        books_to_import = []

        logger.info(f"开始去重检查 {len(books)} 条数据...")

        for book in books:
            title = book.get("title", "")
            author = book.get("author", "")

            # 去重检查
            if self.check_exists(title, author):
                skip_count += 1
                continue

            books_to_import.append(book)

            # 避免请求过快
            time.sleep(0.3)

        if not books_to_import:
            logger.info("没有需要导入的数据（全部重复）")
            return 0, skip_count, 0, []

        logger.info(f"去重完成，待导入 {len(books_to_import)} 条")

        # 批量导入
        result = self.batch_import(books_to_import)

        if result and result.get("success"):
            data = result.get("data", {})
            success_count = data.get("imported", 0)
            skip_count += data.get("skipped", 0)
            error_count = data.get("failed", 0)
            errors = data.get("errors", [])
        else:
            error_count = len(books_to_import)
            errors = [{"error": result.get("error", "未知错误")}]

        return success_count, skip_count, error_count, errors

    def get_books_count(self) -> int:
        """
        获取云数据库中书籍总数

        Returns:
            int: 书籍总数
        """
        import httpx

        if not self.access_token:
            if not self.get_access_token():
                return 0

        url = "https://api.weixin.qq.com/tcb/databasequery"
        params = {"access_token": self.access_token}

        query = "db.collection('books').count()"
        data = {
            "env": self.env_id,
            "query": query
        }

        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(url, params=params, json=data)
                result = response.json()

                if result.get("errcode") == 0:
                    return result.get("pager", {}).get("Total", 0)
                else:
                    logger.error(f"查询总数失败: {result}")
                    return 0
        except Exception as e:
            logger.error(f"查询总数异常: {e}")
            return 0
