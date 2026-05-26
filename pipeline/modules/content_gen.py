"""
AI文稿生成模块
使用豆包API生成18分钟深度解读文稿+金句
"""
import time
try:
    from volcenginesdkarkruntime import Ark
except ImportError:
    from volcengine_python_sdk.ark.runtime import Ark  # fallback for newer versions


CONTENT_PROMPT = """你是一位资深文学解读专家，请为《{book_name}》生成一篇18分钟的深度解读文稿，字数约4500字，严格按照以下结构写作：

1. 开篇引入（300字）：介绍书籍地位、获奖情况、全球影响力
2. 时代背景（500字）：作者生平、创作背景、所处的社会环境
3. 故事梗概（800字）：清晰讲述全书主线剧情，不剧透关键结局
4. 核心人物分析（1000字）：深度解析3-4个主要人物的性格与命运
5. 核心主题解读（1200字）：剖析书籍传递的核心思想与价值观
6. 经典金句赏析（400字）：摘录5句书中最经典的句子并解读
7. 结尾升华（300字）：总结书籍的现实意义与对当代人的启示

要求：
- 语言口语化，适合音频朗读，避免过于学术化的表达
- 每段结尾标注[停顿0.5s]，重要观点前标注[强调]
- 不要出现任何markdown格式，纯文本输出
"""


class ContentGenerator:
    def __init__(self, config):
        self.api_key = config.doubao.get("api_key")
        self.base_url = config.doubao.get("base_url")
        self.model = config.doubao.get("model", "ep-20240512xxxxxx")
        self.client = None

        if self.api_key and self.api_key != "你的豆包API密钥":
            self.client = Ark(api_key=self.api_key, base_url=self.base_url)

    def generate(self, book_info):
        """
        为书籍生成解读文稿和金句
        返回: dict 包含 script, quotes, script_path
        """
        book_name = book_info.get("name", "未知书名")
        author = book_info.get("author", "未知作者")
        print(f"  [AI文稿] 正在生成《{book_name}》解读...")

        if not self.client:
            print(f"  [AI文稿] 未配置API，使用模拟文稿")
            return self._mock_content(book_name, author)

        try:
            # 生成完整文稿
            prompt = CONTENT_PROMPT.format(book_name=book_name)
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一位资深文学解读专家，擅长生成适合音频朗读的通俗文学解读文章。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=8000
            )
            script = response.choices[0].message.content
            print(f"  [AI文稿] 文稿生成完成，约{len(script)}字")

            # 提取金句（从文稿中提取5-10条经典句子）
            quotes = self._extract_quotes(script, book_name)
            print(f"  [AI文稿] 金句提取完成，共{len(quotes)}条")

            return {
                "script": script,
                "quotes": quotes,
                "author": author
            }

        except Exception as e:
            print(f"  [AI文稿] 生成失败: {e}，使用模拟文稿")
            return self._mock_content(book_name, author)

    def _extract_quotes(self, script, book_name):
        """从文稿中提取金句"""
        # 如果文稿中已包含金句部分，尝试提取
        quotes = []

        # 简单规则：从"他说："、"正如...所说"等模式中提取
        lines = script.split('\n')
        for line in lines:
            line = line.strip()
            # 过滤短句，保留10-50字的中文句子
            if 10 <= len(line) <= 60 and '。' in line:
                # 排除纯描述性句子
                if any(kw in line for kw in ['说', '道', '言', '指出', '认为', '"', '"']):
                    quotes.append(line.replace('"', '"').replace('"', '"'))

        # 返回最多10条
        return quotes[:10]

    def _mock_content(self, book_name, author):
        """模拟文稿数据（测试用）"""
        script = f"""[停顿0.5s]

[强调]欢迎来到今天的读书分享，让我们一起走进《{book_name}》的世界。

[停顿0.5s]

一、开篇引入

说起《{book_name}》，这是一部由著名作家{author}创作的经典作品，在中国文学史上有着举足轻重的地位。

[停顿0.5s]

二、时代背景

这部作品创作于一个特殊的时代背景下，当时社会正在经历深刻的变革...

[停顿0.5s]

三、故事梗概

故事的主人公经历了人生的起起落落，从最初的...到后来的...整个叙事结构宏大而精妙。

[停顿0.5s]

四、核心人物分析

书中的几个主要人物各有特色，他们的命运轨迹反映了深刻的社会现实...

[停顿0.5s]

五、核心主题解读

这部作品探讨了...等永恒的主题，在今天依然具有强烈的现实意义。

[停顿0.5s]

六、经典金句赏析

让我们一起来品味书中的经典语句...

[停顿0.5s]

七、结尾升华

总的来说，《{book_name}》是一部值得反复品读的佳作，它带给我们的思考远不止于故事本身。"""

        quotes = [
            f"生活不可能像你想象的那么好，但也不会像你想象的那么糟。——《{book_name}》",
            f"人的一生应当有一次，不因虚度年华而悔恨。——《{book_name}》",
            f"世界上只有一种真正的英雄主义，那就是认清生活的真相后依然热爱生活。——《{book_name}》",
            f"生命中真正重要的不是你遭遇了什么，而是你记住了哪些事，又是如何铭记的。——《{book_name}》",
            f"我们听过无数的道理，却仍旧过不好这一生。——《{book_name}》"
        ]

        return {
            "script": script,
            "quotes": quotes,
            "author": author
        }
