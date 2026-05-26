"""
MiniMax API 客户端
使用 Anthropic 兼容格式调用 MiniMax 文生文接口生成书籍文稿
"""
import os
import re
import logging
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)


class MiniMaxClient:
    """MiniMax API 客户端 - Anthropic 兼容格式"""

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        """
        初始化 MiniMax 客户端

        Args:
            api_key: MiniMax API 密钥，默认从环境变量 ANTHROPIC_API_KEY 读取
            base_url: API 基础URL，默认从环境变量 ANTHROPIC_BASE_URL 读取
        """
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.base_url = base_url or os.getenv("ANTHROPIC_BASE_URL", "https://api.minimax.chat/v1")

        if not self.api_key:
            raise ValueError("缺少 MiniMax API 密钥！请设置 ANTHROPIC_API_KEY 环境变量")

        # 使用 anthropic 包（与 MiniMax 兼容）
        try:
            from anthropic import Anthropic
            self.client = Anthropic(api_key=self.api_key, base_url=self.base_url)
        except ImportError:
            logger.warning("未安装 anthropic 包，尝试使用 httpx")
            self.client = None

    def generate_script(self, title: str, author: str, description: str = "",
                       max_tokens: int = 4000, temperature: float = 0.7) -> str:
        """
        使用 MiniMax 生成书籍朗读文稿

        Args:
            title: 书名
            author: 作者
            description: 书籍简介
            max_tokens: 最大生成 token 数
            temperature: 温度参数 (0.0-1.0)

        Returns:
            str: 生成的文稿内容
        """
        prompt = f"""请为以下书籍生成一段朗读文稿（约4000字）：

书名：《{title}》
作者：{author}
简介：{description if description else '暂无简介'}

要求：
1. 文稿要适合朗读，语句流畅自然
2. 包含书籍背景、核心内容、精彩片段
3. 包含3-5句经典金句
4. 分段清晰，便于制作字幕
5. 每段结尾可标注[停顿]标记

请直接生成文稿内容，不要加标题。"""

        if self.client:
            try:
                response = self.client.messages.create(
                    model="MiniMax-Text-01",
                    max_tokens=max_tokens,
                    temperature=temperature,
                    messages=[
                        {"role": "user", "content": prompt}
                    ]
                )
                return response.content[0].text
            except Exception as e:
                logger.error(f"MiniMax API 调用失败: {e}")
                raise
        else:
            # 降级方案：使用 httpx 直接调用
            return self._generate_with_httpx(prompt, max_tokens, temperature)

    def _generate_with_httpx(self, prompt: str, max_tokens: int, temperature: float) -> str:
        """使用 httpx 调用 MiniMax API（降级方案）"""
        import httpx

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01"
        }

        payload = {
            "model": "MiniMax-Text-01",
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}]
        }

        with httpx.Client(timeout=120.0) as client:
            response = client.post(
                f"{self.base_url}/messages",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            result = response.json()
            return result["content"][0]["text"]

    @staticmethod
    def split_sentences(text: str) -> List[str]:
        """
        将文稿分割成句子数组

        Args:
            text: 文稿文本

        Returns:
            List[str]: 句子数组
        """
        # 按常见分隔符分割
        sentences = re.split(r'[。！？\n]+', text)
        # 过滤空句子并去除首尾空格
        sentences = [s.strip() for s in sentences if s.strip()]
        return sentences

    @staticmethod
    def format_for_import(book: Dict, script: str, sentences: List[str]) -> Dict:
        """
        格式化数据用于导入到云数据库

        Args:
            book: 原始书籍数据
            script: 生成的文稿
            sentences: 分割后的句子数组

        Returns:
            Dict: 格式化后的数据
        """
        import time
        now = int(time.time() * 1000)

        return {
            **book,
            "title": book.get("title", ""),
            "author": book.get("author", ""),
            "category": book.get("category", 1),
            "categoryName": book.get("categoryName", "其他"),
            "publisher": book.get("publisher", ""),
            "isbn": book.get("isbn", ""),
            "description": book.get("description", ""),
            "coverColor": book.get("coverColor", "#3498DB"),
            "coverUrl": book.get("coverUrl", ""),
            "script": script,
            "scriptLength": len(script),
            "sentences": sentences,
            "audioUrl": book.get("audioUrl", ""),
            "audioDuration": book.get("audioDuration", 0),
            "isAudioGenerated": book.get("isAudioGenerated", False),
            "isHot": book.get("isHot", False),
            "isGenerated": True,
            "isPublished": True,
            "viewCount": 0,
            "playCount": 0,
            "qualityScore": book.get("qualityScore", 80),
            "source": book.get("source", "minimax"),
            "createTime": book.get("createTime") or now,
            "updateTime": now
        }

    def close(self):
        """关闭客户端连接"""
        if self.client and hasattr(self.client, 'close'):
            self.client.close()
