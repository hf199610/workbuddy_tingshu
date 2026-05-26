"""
TTS音频合成模块
使用火山引擎TTS将文稿转换为音频
"""
import os
import time
import base64
import hashlib
import hmac
import json
import requests
from pathlib import Path
from datetime import datetime


class TTSEngine:
    def __init__(self, config):
        self.access_key = config.tts.get("access_key")
        self.secret_key = config.tts.get("secret_key")
        self.app_id = config.tts.get("app_id")
        self.voice_type = config.tts.get("voice_type", "BV700_V2")
        self.base_url = "https://openspeech.bytedance.com/api/v1/tts"

        self.authorized = all([
            self.access_key and self.access_key != "你的AccessKey",
            self.secret_key and self.secret_key != "你的SecretKey",
            self.app_id and self.app_id != "你的项目AppID"
        ])

    def synthesize(self, text, output_path, book_name=""):
        """
        将文本合成为音频
        返回: str 音频文件路径
        """
        print(f"  [TTS合成] 开始合成《{book_name}》音频...")

        if not self.authorized:
            print(f"  [TTS合成] 未配置API，创建模拟音频占位文件")
            return self._create_placeholder(output_path, book_name, text)

        try:
            # 火山引擎TTS API调用
            headers = {
                "Content-Type": "application/json",
                "Authorization": self._get_authorization(),
            }

            # 文稿分段（每次最多500字）
            segments = self._split_text(text, max_chars=450)
            audio_data_list = []

            for i, segment in enumerate(segments):
                print(f"  [TTS合成] 正在合成第{i+1}/{len(segments)}段...")
                payload = {
                    "appid": self.app_id,
                    "voice_type": self.voice_type,
                    "text": segment,
                    "encoding": "wav",  # 先用wav保证质量，后续可转mp3
                    "speed_ratio": 1.0,
                    "volume_ratio": 1.0,
                    "pitch_ratio": 1.0,
                    "emotion": "neutral",
                }

                response = requests.post(
                    self.base_url,
                    headers=headers,
                    data=json.dumps(payload),
                    timeout=60
                )

                if response.status_code == 200:
                    result = response.json()
                    if result.get("data"):
                        audio_data_list.append(result["data"])
                else:
                    print(f"  [TTS合成] 第{i+1}段合成失败: {response.status_code}")

                time.sleep(0.3)  # 避免请求过快

            # 合并音频片段并保存
            if audio_data_list:
                final_path = self._save_audio(audio_data_list, output_path)
                print(f"  [TTS合成] 音频保存至: {final_path}")
                return final_path
            else:
                return self._create_placeholder(output_path, book_name, text)

        except Exception as e:
            print(f"  [TTS合成] 合成失败: {e}，创建占位文件")
            return self._create_placeholder(output_path, book_name, text)

    def _get_authorization(self):
        """生成鉴权Token（简化版，实际用火山引擎签名）"""
        # 实际需要按火山引擎文档生成签名
        # 这里返回Bearer Token格式
        return f"Bearer;{self.access_key}"

    def _split_text(self, text, max_chars=450):
        """将长文本分段"""
        # 按句子分段
        sentences = []
        current = ""

        for char in text:
            current += char
            if char in '。！？\n':
                if len(current) >= max_chars // 2:
                    sentences.append(current.strip())
                    current = ""

        if current.strip():
            sentences.append(current.strip())

        # 合并过短的段落
        result = []
        buffer = ""
        for seg in sentences:
            if len(buffer) + len(seg) <= max_chars:
                buffer += seg + "。"
            else:
                if buffer:
                    result.append(buffer)
                buffer = seg

        if buffer:
            result.append(buffer)

        return result if result else [text[:max_chars]]

    def _save_audio(self, audio_data_list, output_path):
        """保存音频数据"""
        output_dir = Path(output_path).parent
        output_dir.mkdir(parents=True, exist_ok=True)

        # 合并所有音频数据块
        all_data = b""
        for data_b64 in audio_data_list:
            audio_bytes = base64.b64decode(data_b64)
            all_data += audio_bytes

        with open(output_path, "wb") as f:
            f.write(all_data)

        return str(output_path)

    def _create_placeholder(self, output_path, book_name, text):
        """创建占位文件（测试用）"""
        output_dir = Path(output_path).parent
        output_dir.mkdir(parents=True, exist_ok=True)

        # 创建一个简短的文本说明文件作为占位
        info_path = output_path.replace(".wav", "_info.txt")
        with open(info_path, "w", encoding="utf-8") as f:
            f.write(f"""音频占位说明
================
书名：{book_name}
文稿字数：{len(text)}字
预计音频时长：约{len(text)//350}分钟
状态：待TTS合成

提示：请配置火山引擎TTS API密钥后重新运行以生成真实音频。
""")

        # 创建空音频占位文件
        Path(output_path).touch()
        print(f"  [TTS合成] 占位文件已创建: {info_path}")
        return str(output_path)
