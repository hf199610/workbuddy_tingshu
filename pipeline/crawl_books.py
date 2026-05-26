#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
完整数据源爬取脚本
支持：豆瓣搜索 + 阿里云API 双源爬取书籍基础信息
输出：JSON格式，可直接喂给字幕生成脚本

使用方法:
  python crawl_books.py                       # 爬取默认书单
  python crawl_books.py --source douban       # 只用豆瓣
  python crawl_books.py --source aliyun       # 只用阿里云API
  python crawl_books.py --books "活着,三体"    # 指定书名
  python crawl_books.py --file book_list.txt  # 从文件读取书名
"""

import os
import re
import sys
import json
import time
import random
import logging
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

import httpx

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)

# ==================== 分类对照表 ====================
CATEGORY_MAP = {
    1: "经典名著", 2: "儿童文学", 3: "科普百科",
    4: "历史传记", 5: "哲学心理", 6: "文学小说",
    7: "诗词歌赋", 8: "家庭教育", 9: "成长励志",
    10: "科幻悬疑", 11: "散文随笔", 12: "其他"
}

CATEGORY_KEYWORDS = {
    1: ["名著", "经典", "四大名著", "红楼梦", "三国", "水浒", "西游"],
    2: ["儿童", "童话", "绘本", "少年", "小王子", "小豆豆"],
    3: ["科普", "百科", "科学", "宇宙", "物理", "化学", "十万个"],
    4: ["历史", "传记", "史记", "人物", "帝王", "朝代"],
    5: ["哲学", "心理", "思维", "逻辑", "禅", "冥想", "瓦尔登湖"],
    6: ["小说", "文学", "故事", "虚构", "余华", "路遥", "莫言"],
    7: ["诗词", "诗歌", "唐诗", "宋词", "诗经", "古文"],
    8: ["教育", "家庭", "育儿", "管教", "妈妈", "亲子"],
    9: ["励志", "成长", "奋斗", "成功", "钢铁"],
    10: ["科幻", "悬疑", "推理", "三体", "东野", "侦探"],
    11: ["散文", "随笔", "杂文", "游记", "三毛", "鲁迅"],
    12: ["其他"]
}

# ==================== 配置 ====================
DATA_DIR = Path(__file__).parent.parent / "data_source"
CRAWLED_FILE = DATA_DIR / "crawled_books.json"
OUTPUT_FILE = DATA_DIR / "crawled_output.json"
FAILED_FILE = DATA_DIR / "crawl_failed.json"

# 阿里云API配置（从环境变量读取）
ALIYUN_APP_CODE = os.getenv("ALIYUN_APP_CODE", "")

# 默认书单
DEFAULT_BOOKS = [
    "小王子", "红楼梦", "活着", "平凡的世界", "三体",
    "解忧杂货店", "百年孤独", "围城", "追风筝的人",
    "人类简史", "时间简史", "窗边的小豆豆", "夏洛的网",
    "西游记", "三国演义", "水浒传", "史记",
    "瓦尔登湖", "钢铁是怎样炼成的", "撒哈拉的故事",
    "唐诗三百首", "诗经", "好妈妈胜过好老师", "正面管教",
    "苏东坡传", "十万个为什么"
]


def auto_classify(title: str, author: str = "", description: str = "") -> tuple:
    """根据书名/作者/简介自动推断分类"""
    text = f"{title} {author} {description}"
    for cat_id, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                return cat_id, CATEGORY_MAP[cat_id]
    return 12, "其他"


def generate_cover_color(title: str) -> str:
    """根据书名生成封面背景色"""
    colors = [
        '#8B4513', '#FF6B6B', '#4ECDC4', '#9B59B6', '#3498DB',
        '#E74C3C', '#F39C12', '#27AE60', '#1ABC9C', '#2C3E50',
        '#E67E22', '#95A5A6', '#DDA0DD', '#87CEEB', '#F0E68C'
    ]
    index = sum(ord(c) for c in title) % len(colors)
    return colors[index]


def load_crawled_records() -> set:
    """加载已爬取的书名记录，用于去重"""
    if CRAWLED_FILE.exists():
        try:
            with open(CRAWLED_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return set(item.get("name", "") for item in data)
        except Exception:
            pass
    return set()


def save_crawled_record(name: str):
    """保存爬取记录"""
    records = []
    if CRAWLED_FILE.exists():
        try:
            with open(CRAWLED_FILE, 'r', encoding='utf-8') as f:
                records = json.load(f)
        except Exception:
            pass
    records.append({"name": name, "crawlTime": int(time.time() * 1000)})
    with open(CRAWLED_FILE, 'w', encoding='utf-8') as f:
        json.dump(records, f, ensure_ascii=False, indent=2)


# ==================== 豆瓣搜索爬虫 ====================
class DoubanCrawler:
    """豆瓣读书搜索爬虫"""

    SEARCH_URL = "https://search.douban.com/book/subject_search"
    DETAIL_URL = "https://book.douban.com/subject/{subject_id}/"

    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Referer': 'https://book.douban.com/',
    }

    def __init__(self):
        self.client = httpx.Client(
            headers=self.HEADERS,
            follow_redirects=True,
            timeout=30.0
        )

    def search_book(self, book_name: str) -> Optional[Dict]:
        """搜索书籍，返回基础信息"""
        logger.info(f"[豆瓣] 搜索: 《{book_name}》")

        try:
            # 方法1: 通过搜索页面API获取
            resp = self.client.get(
                "https://www.douban.com/j/search",
                params={
                    "q": book_name,
                    "cat": "1001",  # 图书分类
                    "start": 0,
                    "count": 5
                }
            )

            if resp.status_code == 200:
                data = resp.json()
                items = data.get("items", [])
                if items:
                    # 解析搜索结果中的HTML
                    for item in items:
                        html_content = item.get("content", "")
                        # 提取subject ID
                        sid_match = re.search(r'subject/(\d+)', html_content)
                        title_match = re.search(r'title="([^"]+)"', html_content)

                        if sid_match:
                            subject_id = sid_match.group(1)
                            result_title = title_match.group(1) if title_match else book_name
                            # 获取详情
                            detail = self._get_detail(subject_id)
                            if detail:
                                detail["title"] = book_name  # 用搜索关键词作为标题
                                return detail

            # 方法2: 直接尝试搜索页面
            return self._search_via_page(book_name)

        except Exception as e:
            logger.error(f"[豆瓣] 搜索失败: {e}")
            return None

    def _search_via_page(self, book_name: str) -> Optional[Dict]:
        """通过搜索页面获取书籍信息（备用方法）"""
        try:
            resp = self.client.get(
                self.SEARCH_URL,
                params={"search_text": book_name, "cat": "1001"}
            )
            if resp.status_code == 200:
                # 尝试从页面JSON数据中提取
                json_match = re.search(r'window\.__DATA__\s*=\s*(".*?")\s*</script>', resp.text, re.DOTALL)
                if json_match:
                    # 豆瓣搜索结果数据在 window.__DATA__ 中
                    import json as json_lib
                    raw = json_lib.loads(json_lib.loads(json_match.group(1)))
                    if raw and len(raw) > 0:
                        items = raw[0].get("items", [])
                        if items:
                            first = items[0]
                            return {
                                "title": first.get("title", book_name),
                                "author": self._extract_author(first.get("abstract", "")),
                                "publisher": self._extract_publisher(first.get("abstract", "")),
                                "isbn": first.get("isbn", ""),
                                "description": first.get("abstract", ""),
                                "coverUrl": first.get("cover_url", ""),
                                "score": first.get("rating", {}).get("value", 0),
                                "sourceUrl": f"https://book.douban.com/subject/{first.get('id', '')}/",
                                "source": "douban",
                                "crawlTime": int(time.time() * 1000),
                            }
        except Exception as e:
            logger.error(f"[豆瓣] 页面搜索失败: {e}")
        return None

    def _get_detail(self, subject_id: str) -> Optional[Dict]:
        """获取书籍详情页"""
        try:
            url = self.DETAIL_URL.format(subject_id=subject_id)
            resp = self.client.get(url)

            if resp.status_code != 200:
                return None

            html = resp.text

            # 提取信息
            info_section = self._extract_info_section(html)

            return {
                "author": info_section.get("author", "未知作者"),
                "publisher": info_section.get("publisher", ""),
                "isbn": info_section.get("isbn", ""),
                "publishDate": info_section.get("publishDate", ""),
                "pages": info_section.get("pages", 0),
                "description": self._extract_description(html),
                "score": self._extract_score(html),
                "coverUrl": self._extract_cover(html),
                "sourceUrl": url,
                "source": "douban",
                "crawlTime": int(time.time() * 1000),
            }
        except Exception as e:
            logger.error(f"[豆瓣] 详情获取失败: {e}")
            return None

    def _extract_info_section(self, html: str) -> Dict:
        """从HTML的info区域提取结构化数据"""
        result = {
            "author": "未知作者",
            "publisher": "",
            "isbn": "",
            "publishDate": "",
            "pages": 0
        }

        # 提取作者
        author_match = re.search(r'<span\s+class="pl">作者</span>.*?<a[^>]*>([^<]+)</a>', html, re.DOTALL)
        if author_match:
            result["author"] = author_match.group(1).strip()
        else:
            author_match2 = re.search(r'作者[:\s]*([^<\n/]+)', html)
            if author_match2:
                result["author"] = author_match2.group(1).strip().rstrip("/")

        # 提取出版社
        pub_match = re.search(r'出版社[:\s]*([^<\n/]+)', html)
        if pub_match:
            result["publisher"] = pub_match.group(1).strip().rstrip("/")

        # 提取ISBN
        isbn_match = re.search(r'ISBN[:\s]*([\d-]+)', html)
        if isbn_match:
            result["isbn"] = isbn_match.group(1).strip()

        # 提取出版年
        date_match = re.search(r'出版年[:\s]*(\d{4})', html)
        if date_match:
            result["publishDate"] = date_match.group(1)

        # 提取页数
        pages_match = re.search(r'页数[:\s]*(\d+)', html)
        if pages_match:
            result["pages"] = int(pages_match.group(1))

        return result

    def _extract_description(self, html: str) -> str:
        """提取书籍简介"""
        # 方法1: 从intro区域提取
        intro_match = re.search(r'<div class="intro">([\s\S]*?)</div>', html)
        if intro_match:
            text = re.sub(r'<[^>]+>', '', intro_match.group(1))
            return text.strip()[:500]

        # 方法2: 从description meta标签提取
        desc_match = re.search(r'"description"\s*:\s*"([^"]+)"', html)
        if desc_match:
            return desc_match.group(1).strip()[:500]

        return ""

    def _extract_score(self, html: str) -> float:
        """提取评分"""
        score_match = re.search(r'<strong class="ll rating_num"[^>]*>\s*([\d.]+)\s*</strong>', html)
        if score_match:
            return float(score_match.group(1))
        return 0.0

    def _extract_cover(self, html: str) -> str:
        """提取封面图URL"""
        cover_match = re.search(r'<img[^>]*src="([^"]*book.douban.com[^"]*)"[^>]*', html)
        if cover_match:
            return cover_match.group(1)
        return ""

    def _extract_author(self, text: str) -> str:
        """从文本中提取作者名"""
        match = re.search(r'作者[：:]\s*([^/\n]+)', text)
        if match:
            return match.group(1).strip()
        return "未知作者"

    def _extract_publisher(self, text: str) -> str:
        """从文本中提取出版社"""
        match = re.search(r'出版社[：:]\s*([^/\n]+)', text)
        if match:
            return match.group(1).strip()
        return ""

    def close(self):
        self.client.close()


# ==================== 阿里云API爬虫 ====================
class AliyunCrawler:
    """阿里云市场-图书信息查询API"""

    API_URL = "https://bookinfo.market.alicloudapi.com/bookinfo"

    def __init__(self, app_code: str = ""):
        self.app_code = app_code or ALIYUN_APP_CODE
        if not self.app_code:
            logger.warning("[阿里云] 未配置APPCODE，无法使用阿里云API")
            self.client = None
            return

        self.client = httpx.Client(
            headers={
                "Authorization": f"APPCODE {self.app_code}",
                "Content-Type": "application/x-www-form-urlencoded"
            },
            timeout=30.0
        )

    def search_book(self, book_name: str) -> Optional[Dict]:
        """通过阿里云API搜索书籍"""
        if not self.client:
            return None

        logger.info(f"[阿里云] 搜索: 《{book_name}》")

        try:
            resp = self.client.get(
                self.API_URL,
                params={"name": book_name}
            )

            if resp.status_code == 200:
                data = resp.json()

                # 阿里云API返回格式适配
                if isinstance(data, dict):
                    # 检查是否有数据
                    books = data.get("data", data.get("result", []))
                    if isinstance(books, list) and len(books) > 0:
                        book = books[0]
                    elif isinstance(data, dict) and data.get("name"):
                        book = data
                    else:
                        logger.warning(f"[阿里云] 未找到: 《{book_name}》")
                        return None

                    return {
                        "title": book.get("name", book_name),
                        "author": book.get("author", "未知作者"),
                        "publisher": book.get("publisher", ""),
                        "isbn": book.get("isbn", ""),
                        "publishDate": book.get("publishDate", book.get("pubdate", "")),
                        "pages": int(book.get("pages", 0) or 0),
                        "description": book.get("intro", book.get("description", ""))[:500],
                        "coverUrl": book.get("cover", book.get("coverUrl", "")),
                        "score": float(book.get("score", book.get("rating", 0)) or 0),
                        "sourceUrl": book.get("url", ""),
                        "source": "aliyun",
                        "crawlTime": int(time.time() * 1000),
                    }
            else:
                logger.error(f"[阿里云] API调用失败: HTTP {resp.status_code}")
                return None

        except Exception as e:
            logger.error(f"[阿里云] 搜索失败: {e}")
            return None

    def close(self):
        if self.client:
            self.client.close()


# ==================== 手动补充数据 ====================
MANUAL_BOOKS = {
    "小王子": {
        "author": "安托万·德·圣-埃克苏佩里",
        "category": 2, "categoryName": "儿童文学",
        "publisher": "人民文学出版社",
        "isbn": "978-7-0200-0987-8",
        "description": "这是一本足以让人永葆童心的不朽经典，被全球亿万读者誉为最值得收藏的书。《小王子》透过孩子般的眼光，透视出成人的空虚、盲目和愚钝，用最天真的话语道出深刻的人生哲理。"
    },
    "红楼梦": {
        "author": "曹雪芹",
        "category": 1, "categoryName": "经典名著",
        "publisher": "人民文学出版社",
        "isbn": "978-7-0200-0829-1",
        "description": "中国古典四大名著之一，以贾、史、王、薛四大家族的兴衰为背景，以贾宝玉、林黛玉、薛宝钗的爱情婚姻故事为主线，刻画了封建社会末期的种种矛盾和冲突。"
    },
    "活着": {
        "author": "余华",
        "category": 6, "categoryName": "文学小说",
        "publisher": "作家出版社",
        "isbn": "978-7-5059-5034-9",
        "description": "讲述了农村人福贵悲惨的人生遭遇。福贵本是个阔少爷，可他嗜赌如命，终于赌光了家业，一贫如洗。他的父亲被他活活气死，母亲则在穷困中患了重病。"
    },
    "平凡的世界": {
        "author": "路遥",
        "category": 6, "categoryName": "文学小说",
        "publisher": "人民文学出版社",
        "isbn": "978-7-0200-4804-4",
        "description": "以中国70年代中期到80年代中期十年间为背景，通过复杂的矛盾纠葛，以孙少安和孙少平两兄弟为中心，刻画了当时社会各阶层众多普通人的形象。"
    },
    "三体": {
        "author": "刘慈欣",
        "category": 10, "categoryName": "科幻悬疑",
        "publisher": "重庆出版社",
        "isbn": "978-7-5366-7784-5",
        "description": "讲述了地球人类文明和三体文明之间的信息交流、生死搏杀及两个文明在宇宙中的兴衰历程，荣获第73届雨果奖最佳长篇小说奖。"
    },
    "解忧杂货店": {
        "author": "东野圭吾",
        "category": 10, "categoryName": "科幻悬疑",
        "publisher": "南海出版公司",
        "isbn": "978-7-5442-7201-6",
        "description": "僻静的街道旁有一家杂货店，只要写下烦恼投进卷帘门的投信口，第二天就会在店后的牛奶箱里得到回答。"
    },
    "百年孤独": {
        "author": "加西亚·马尔克斯",
        "category": 6, "categoryName": "文学小说",
        "publisher": "南海出版公司",
        "isbn": "978-7-5442-4528-8",
        "description": "魔幻现实主义文学的代表作，描写了布恩迪亚家族七代人的传奇故事，以及加勒比海沿岸小镇马孔多的百年兴衰。"
    },
    "围城": {
        "author": "钱钟书",
        "category": 6, "categoryName": "文学小说",
        "publisher": "人民文学出版社",
        "isbn": "978-7-0200-2806-4",
        "description": "以抗战初期为背景，以方鸿渐的生活道路为主线，刻画了那个时代某些知识分子精神的空虚和彷徨。"
    },
    "追风筝的人": {
        "author": "卡勒德·胡赛尼",
        "category": 6, "categoryName": "文学小说",
        "publisher": "上海人民出版社",
        "isbn": "978-7-2080-6164-4",
        "description": "12岁的阿富汗富家少爷阿米尔与仆人哈桑情同手足，然而在一场风筝比赛后，发生了一件悲惨不堪的事。"
    },
    "人类简史": {
        "author": "尤瓦尔·赫拉利",
        "category": 3, "categoryName": "科普百科",
        "publisher": "中信出版社",
        "isbn": "978-7-5086-4456-9",
        "description": "从十万年前有生命迹象开始到21世纪资本、科技交织的人类发展史，理清了影响人类发展的重大脉络。"
    },
    "时间简史": {
        "author": "斯蒂芬·霍金",
        "category": 3, "categoryName": "科普百科",
        "publisher": "湖南科学技术出版社",
        "isbn": "978-7-5357-4729-5",
        "description": "一部将高深的理论物理通俗化的科普范本，解释了宇宙、黑洞和时间等概念，让普通读者也能理解宇宙的起源和命运。"
    },
    "窗边的小豆豆": {
        "author": "黑柳彻子",
        "category": 2, "categoryName": "儿童文学",
        "publisher": "南海出版公司",
        "isbn": "978-7-5442-4750-3",
        "description": "讲述了作者上小学时的一段真实的故事：小豆豆因淘气被原学校退学后，来到巴学园。"
    },
    "夏洛的网": {
        "author": "E.B.怀特",
        "category": 2, "categoryName": "儿童文学",
        "publisher": "上海译文出版社",
        "isbn": "978-7-5327-4819-1",
        "description": "在朱克曼家的谷仓里，小猪威尔伯和蜘蛛夏洛建立了最真挚的友谊。"
    },
    "西游记": {
        "author": "吴承恩",
        "category": 1, "categoryName": "经典名著",
        "publisher": "人民文学出版社",
        "isbn": "978-7-0200-0729-4",
        "description": "中国古典四大名著之一，讲述了唐僧师徒四人西天取经的故事。"
    },
    "三国演义": {
        "author": "罗贯中",
        "category": 1, "categoryName": "经典名著",
        "publisher": "人民文学出版社",
        "isbn": "978-7-0200-0718-8",
        "description": "中国古典四大名著之一，描写了从东汉末年到西晋初年之间近105年的历史风云。"
    },
    "水浒传": {
        "author": "施耐庵",
        "category": 1, "categoryName": "经典名著",
        "publisher": "人民文学出版社",
        "isbn": "978-7-0200-0728-7",
        "description": "中国古典四大名著之一，以宋江领导的农民起义为主要内容。"
    },
    "史记": {
        "author": "司马迁",
        "category": 4, "categoryName": "历史传记",
        "publisher": "中华书局",
        "isbn": "978-7-1010-3707-9",
        "description": "中国历史上第一部纪传体通史，被鲁迅誉为'史家之绝唱，无韵之离骚'。"
    },
    "瓦尔登湖": {
        "author": "亨利·戴维·梭罗",
        "category": 5, "categoryName": "哲学心理",
        "publisher": "上海译文出版社",
        "isbn": "978-7-5327-4032-4",
        "description": "记录了作者在瓦尔登湖畔两年多的生活经历，对自然、人生、物质等进行了深刻思考。"
    },
    "钢铁是怎样炼成的": {
        "author": "尼古拉·奥斯特洛夫斯基",
        "category": 9, "categoryName": "成长励志",
        "publisher": "人民文学出版社",
        "isbn": "978-7-0200-0939-8",
        "description": "通过对保尔·柯察金成长经历的叙述，生动地展现了苏联广阔的历史画面。"
    },
    "撒哈拉的故事": {
        "author": "三毛",
        "category": 11, "categoryName": "散文随笔",
        "publisher": "北京十月文艺出版社",
        "isbn": "978-7-5302-1466-2",
        "description": "描写了三毛和荷西在撒哈拉沙漠生活时的所见所闻。"
    },
    "唐诗三百首": {
        "author": "蘅塘退士 编",
        "category": 7, "categoryName": "诗词歌赋",
        "publisher": "中华书局",
        "isbn": "978-7-1010-5361-1",
        "description": "中国古代诗歌史上最重要的选本之一，收录了唐代著名诗人的代表作品。"
    },
    "诗经": {
        "author": "佚名",
        "category": 7, "categoryName": "诗词歌赋",
        "publisher": "中华书局",
        "isbn": "978-7-1010-5532-5",
        "description": "中国最早的诗歌总集，共311篇，反映了周初至周晚期约五百年间的社会面貌。"
    },
    "好妈妈胜过好老师": {
        "author": "尹建莉",
        "category": 8, "categoryName": "家庭教育",
        "publisher": "作家出版社",
        "isbn": "978-7-5059-6464-3",
        "description": "是尹建莉的第一部家庭教育著作，提出'不管是最好的管'等教育理念。"
    },
    "正面管教": {
        "author": "简·尼尔森",
        "category": 8, "categoryName": "家庭教育",
        "publisher": "北京联合出版公司",
        "isbn": "978-7-5502-9816-7",
        "description": "正面管教是一种既不惩罚也不娇纵的管教孩子的方法。"
    },
    "苏东坡传": {
        "author": "林语堂",
        "category": 4, "categoryName": "历史传记",
        "publisher": "湖南文艺出版社",
        "isbn": "978-7-5404-7347-3",
        "description": "讲述了苏东坡一个天性豁达、才华横溢的文人的一生。"
    },
    "十万个为什么": {
        "author": "韩启德 主编",
        "category": 3, "categoryName": "科普百科",
        "publisher": "少年儿童出版社",
        "isbn": "978-7-5324-7010-0",
        "description": "是中国最畅销的青少年科普读物，内容涵盖物理、化学、天文、地理、生物等多个学科领域。"
    }
}


def build_book_from_manual(book_name: str) -> Dict:
    """从手动数据构建书籍信息"""
    manual = MANUAL_BOOKS.get(book_name, {})
    cat_id, cat_name = auto_classify(book_name, manual.get("author", ""), manual.get("description", ""))
    now = int(time.time() * 1000)

    return {
        "title": book_name,
        "author": manual.get("author", "未知作者"),
        "category": manual.get("category", cat_id),
        "categoryName": manual.get("categoryName", cat_name),
        "publisher": manual.get("publisher", ""),
        "isbn": manual.get("isbn", ""),
        "publishDate": manual.get("publishDate", ""),
        "pages": manual.get("pages", 0),
        "description": manual.get("description", ""),
        "coverColor": generate_cover_color(book_name),
        "coverUrl": manual.get("coverUrl", ""),
        "score": manual.get("score", 0),
        "source": "manual",
        "sourceUrl": "",
        "crawlTime": now,
        "createTime": now,
        "updateTime": now,
    }


# ==================== 主爬取流程 ====================
def crawl_books(book_names: List[str], source: str = "auto") -> List[Dict]:
    """
    爬取书籍信息

    Args:
        book_names: 书名列表
        source: 数据源 (auto/douban/aliyun/manual)

    Returns:
        List[Dict]: 爬取到的书籍信息列表
    """
    results = []
    failed = []
    crawled_set = load_crawled_records()

    # 初始化爬虫
    douban = DoubanCrawler() if source in ("auto", "douban") else None
    aliyun = AliyunCrawler() if source in ("auto", "aliyun") else None

    total = len(book_names)
    logger.info(f"\n{'='*55}")
    logger.info(f"📚 开始爬取 {total} 本书 | 数据源: {source}")
    logger.info(f"{'='*55}")

    for i, name in enumerate(book_names):
        # 去重检查
        if name in crawled_set:
            logger.info(f"[{i+1}/{total}] ⏭️ 已爬取，跳过: 《{name}》")
            continue

        logger.info(f"\n[{i+1}/{total}] 📖 爬取: 《{name}》")
        book_data = None

        # 尝试各种数据源
        if source == "manual":
            book_data = build_book_from_manual(name)
        else:
            # 1. 先尝试阿里云API（最稳定）
            if aliyun and source in ("auto", "aliyun"):
                book_data = aliyun.search_book(name)
                if book_data:
                    logger.info(f"  ✅ 阿里云API获取成功")

            # 2. 再尝试豆瓣
            if not book_data and douban and source in ("auto", "douban"):
                book_data = douban.search_book(name)
                if book_data:
                    logger.info(f"  ✅ 豆瓣获取成功")

            # 3. 最后用手动数据兜底
            if not book_data and name in MANUAL_BOOKS:
                book_data = build_book_from_manual(name)
                logger.info(f"  ✅ 手动数据兜底")

        if book_data:
            # 确保必要字段
            book_data["title"] = name
            if "category" not in book_data or not book_data.get("category"):
                cat_id, cat_name = auto_classify(name, book_data.get("author", ""), book_data.get("description", ""))
                book_data["category"] = cat_id
                book_data["categoryName"] = cat_name
            if "coverColor" not in book_data:
                book_data["coverColor"] = generate_cover_color(name)

            results.append(book_data)
            save_crawled_record(name)
            logger.info(f"  📊 作者: {book_data.get('author', '未知')} | 分类: {book_data.get('categoryName', '其他')}")
        else:
            # 完全无法获取时，创建最小记录
            cat_id, cat_name = auto_classify(name)
            now = int(time.time() * 1000)
            book_data = {
                "title": name,
                "author": "未知作者",
                "category": cat_id,
                "categoryName": cat_name,
                "publisher": "",
                "isbn": "",
                "description": "",
                "coverColor": generate_cover_color(name),
                "source": "fallback",
                "crawlTime": now,
                "createTime": now,
                "updateTime": now,
            }
            results.append(book_data)
            failed.append({"name": name, "error": "无法获取详细信息"})
            save_crawled_record(name)
            logger.warning(f"  ⚠️ 未能获取《{name}》的详细信息，使用最小记录")

        # 请求间隔（避免被封）
        if i < total - 1:
            delay = random.uniform(2, 5)
            time.sleep(delay)

    # 清理
    if douban:
        douban.close()
    if aliyun:
        aliyun.close()

    # 保存结果
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    logger.info(f"\n💾 爬取结果已保存: {OUTPUT_FILE}")

    if failed:
        with open(FAILED_FILE, 'w', encoding='utf-8') as f:
            json.dump(failed, f, ensure_ascii=False, indent=2)
        logger.info(f"⚠️ 失败记录已保存: {FAILED_FILE}")

    # 汇总
    logger.info(f"\n{'='*55}")
    logger.info(f"📊 爬取汇总")
    logger.info(f"{'='*55}")
    logger.info(f"✅ 成功: {len(results)} 本")
    logger.info(f"❌ 失败: {len(failed)} 本")
    for b in results:
        logger.info(f"  📖 《{b['title']}》- {b.get('author', '未知')} [{b.get('categoryName', '其他')}]")

    return results


# ==================== 入口 ====================
def main():
    parser = argparse.ArgumentParser(description="书籍数据爬取工具")
    parser.add_argument("--source", choices=["auto", "douban", "aliyun", "manual"], default="manual",
                        help="数据源 (auto=自动选择, douban=豆瓣, aliyun=阿里云API, manual=手动数据)")
    parser.add_argument("--books", type=str, help="指定书名，逗号分隔")
    parser.add_argument("--file", type=str, help="从文件读取书名列表")
    args = parser.parse_args()

    # 确定书名列表
    if args.books:
        book_names = [b.strip() for b in args.books.split(",") if b.strip()]
    elif args.file:
        with open(args.file, 'r', encoding='utf-8') as f:
            book_names = [line.strip() for line in f if line.strip() and not line.startswith("#")]
    else:
        book_names = DEFAULT_BOOKS

    # 运行爬取
    results = crawl_books(book_names, source=args.source)

    print(f"\n✅ 爬取完成！共获取 {len(results)} 本书")
    print(f"📁 输出文件: {OUTPUT_FILE}")
    print(f"💡 下一步: python generate_scripts.py --input crawled_output.json")


if __name__ == "__main__":
    main()
