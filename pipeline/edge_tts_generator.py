#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Edge-TTS 音频 + 字幕生成模块
使用微软 Edge-TTS 免费服务生成高质量中文语音，同时生成带时间戳的字幕数据。

使用方法:
  from edge_tts_generator import EdgeTTSGenerator

  gen = EdgeTTSGenerator()
  result = gen.generate(
      text="要朗读的文本内容",
      output_mp3="output/audios/活着.mp3",
      output_vtt="output/subtitles/活着.vtt",
      voice="zh-CN-YunxiNeural"
  )
  # result = { "mp3": path, "vtt": path, "subtitles": [...], "duration_seconds": 120 }

命令行用法:
  python edge_tts_generator.py --input script.txt --output output/audios/test.mp3
  python edge_tts_generator.py --text "你好世界" --output output/audios/test.mp3
"""

import os
import re
import sys
import json
import asyncio
import logging
import argparse
from pathlib import Path
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


# ==================== 字幕合并逻辑 ====================

# 句子结束标点
SENTENCE_ENDINGS = re.compile(r'[。！？\n]')
# [停顿Xs] 标记
PAUSE_PATTERN = re.compile(r'\[停顿\s*(\d+\.?\d*)\s*秒?\]')
# [强调] 等朗读提示标记
HINT_PATTERN = re.compile(r'\[强调\]|\[音乐\]|\[音效\]')


def clean_text_for_tts(text: str) -> str:
    """
    清理文稿中的 TTS 控制标记，生成纯文本用于语音合成。
    保留正常文本内容，移除 [停顿Xs]、[强调] 等标记。
    """
    # 移除所有方括号标记
    cleaned = HINT_PATTERN.sub('', text)
    cleaned = PAUSE_PATTERN.sub('', cleaned)
    # 清理多余空行（保留段落分隔）
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    cleaned = cleaned.strip()
    return cleaned


def merge_words_to_sentences(words: List[Dict]) -> List[Dict]:
    """
    将 word-level 时间戳合并为句子级字幕。
    edge-tts 的 SubMaker 生成 word 级别的时间戳，这里按标点符号合并。

    Args:
        words: SubMaker 生成的 word 列表，每个元素包含 { "text": str, "offset": int, "duration": int }

    Returns:
        句子级字幕列表，每个元素包含 { "index": int, "start": float, "end": float, "text": str }
    """
    if not words:
        return []

    sentences = []
    current_words = []

    for word in words:
        text = word.get("text", "").strip()
        if not text:
            continue

        current_words.append(word)

        # 检查是否是句子结束
        if SENTENCE_ENDINGS.search(text):
            # 合并当前收集的 words 为一个句子
            if current_words:
                sentence = _build_sentence(current_words, len(sentences) + 1)
                if sentence:
                    sentences.append(sentence)
                current_words = []

    # 处理最后剩余的 words
    if current_words:
        sentence = _build_sentence(current_words, len(sentences) + 1)
        if sentence:
            sentences.append(sentence)

    return sentences


def _build_sentence(words: List[Dict], index: int) -> Optional[Dict]:
    """将一组 words 合并为一个句子字典"""
    if not words:
        return None

    # offset 和 duration 的单位是 100 纳秒 (1 tick = 100ns)
    start_offset = words[0].get("offset", 0) / 10_000_000  # 转为秒
    last_word = words[-1]
    end_offset = (last_word.get("offset", 0) + last_word.get("duration", 0)) / 10_000_000

    text = ''.join(w.get("text", "") for w in words).strip()

    if not text or len(text) < 2:
        return None

    return {
        "index": index,
        "start": round(start_offset, 2),
        "end": round(end_offset, 2),
        "text": text
    }


def format_vtt_time(seconds: float) -> str:
    """将秒数格式化为 VTT 时间戳 HH:MM:SS.mmm"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def write_vtt(file_path: str, subtitles: List[Dict]):
    """将字幕数据写入 VTT 文件"""
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write("WEBVTT\n\n")
        for sub in subtitles:
            start = format_vtt_time(sub["start"])
            end = format_vtt_time(sub["end"])
            f.write(f"{start} --> {end}\n")
            f.write(f"{sub['text']}\n\n")


def write_srt(file_path: str, subtitles: List[Dict]):
    """将字幕数据写入 SRT 文件"""
    with open(file_path, 'w', encoding='utf-8') as f:
        for sub in subtitles:
            f.write(f"{sub['index']}\n")
            start = _format_srt_time(sub["start"])
            end = _format_srt_time(sub["end"])
            f.write(f"{start} --> {end}\n")
            f.write(f"{sub['text']}\n\n")


def _format_srt_time(seconds: float) -> str:
    """将秒数格式化为 SRT 时间戳 HH:MM:SS,mmm"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


# ==================== 主生成器类 ====================

class EdgeTTSGenerator:
    """Edge-TTS 音频 + 字幕生成器"""

    # 推荐中文声音列表
    VOICES = {
        "yunxi": "zh-CN-YunxiNeural",       # 男声-云希（自然、年轻）
        "yunxia": "zh-CN-YunxiaNeural",      # 女声-云夏（温柔）
        "yunyang": "zh-CN-YunyangNeural",    # 男声-云扬（新闻播报）
        "xiaoxiao": "zh-CN-XiaoxiaoNeural",  # 女声-晓晓（通用）
        "xiaoyi": "zh-CN-XiaoyiNeural",      # 女声-晓伊（客服）
        "yunze": "zh-CN-YunzeNeural",        # 男声-云泽（成熟）
    }

    DEFAULT_VOICE = "zh-CN-YunxiNeural"
    DEFAULT_RATE = "-5%"       # 语速微调（-100% ~ +200%）
    DEFAULT_PITCH = "-2Hz"     # 音调微调

    def __init__(self, voice: str = None, rate: str = None, pitch: str = None):
        self.voice = voice or self.DEFAULT_VOICE
        self.rate = rate or self.DEFAULT_RATE
        self.pitch = pitch or self.DEFAULT_PITCH
        self._edge_tts = None

    def _ensure_import(self):
        """延迟导入 edge_tts，避免在没有安装时报错"""
        if self._edge_tts is None:
            try:
                import edge_tts
                self._edge_tts = edge_tts
            except ImportError:
                raise ImportError(
                    "edge-tts 未安装。请运行: pip install edge-tts"
                )

    def generate(
        self,
        text: str,
        output_mp3: str,
        output_vtt: str = None,
        output_srt: str = None,
        voice: str = None,
        rate: str = None,
        pitch: str = None,
    ) -> Dict:
        """
        生成音频文件和字幕文件（同步接口，内部调用 async）。

        Args:
            text: 要朗读的文本
            output_mp3: 输出 MP3 文件路径
            output_vtt: 输出 VTT 字幕文件路径（可选）
            output_srt: 输出 SRT 字幕文件路径（可选）
            voice: TTS 声音（可选，使用实例默认值）
            rate: 语速（可选）
            pitch: 音调（可选）

        Returns:
            dict: {
                "mp3": str,                # MP3 文件路径
                "vtt": str|None,           # VTT 文件路径
                "srt": str|None,           # SRT 文件路径
                "subtitles": list[dict],   # 字幕 JSON 数组
                "duration_seconds": float, # 音频时长（秒）
                "text_length": int,        # 文本字数
                "voice": str,              # 使用的声音
            }
        """
        return asyncio.run(self.generate_async(
            text=text,
            output_mp3=output_mp3,
            output_vtt=output_vtt,
            output_srt=output_srt,
            voice=voice,
            rate=rate,
            pitch=pitch,
        ))

    async def generate_async(
        self,
        text: str,
        output_mp3: str,
        output_vtt: str = None,
        output_srt: str = None,
        voice: str = None,
        rate: str = None,
        pitch: str = None,
    ) -> Dict:
        """异步版本"""
        self._ensure_import()
        edge_tts = self._edge_tts

        voice = voice or self.voice
        rate = rate or self.rate
        pitch = pitch or self.pitch

        # 清理文本
        clean_text = clean_text_for_tts(text)
        char_count = len(clean_text)

        if not clean_text.strip():
            raise ValueError("文本内容为空，无法生成音频")

        logger.info(f"🎙️ 开始生成音频: {voice}, 文本 {char_count} 字")

        # 创建 Communicate 对象
        communicate = edge_tts.Communicate(clean_text, voice, rate=rate, pitch=pitch)
        submaker = edge_tts.SubMaker()

        # 确保输出目录存在
        Path(output_mp3).parent.mkdir(parents=True, exist_ok=True)

        # 流式生成音频 + 收集时间戳
        audio_data = bytearray()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data.extend(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                submaker.create_sub(
                    (chunk["offset"], chunk["duration"]),
                    chunk["text"]
                )

        # 写入 MP3 文件
        with open(output_mp3, "wb") as f:
            f.write(audio_data)

        mp3_size = len(audio_data)
        logger.info(f"✅ 音频已保存: {output_mp3} ({mp3_size / 1024:.1f} KB)")

        # 合并为句子级字幕
        subtitles = merge_words_to_sentences(submaker.subs)
        logger.info(f"✅ 字幕生成完成: {len(subtitles)} 句")

        # 估算音频时长（从最后一个字幕的 end 时间）
        duration_seconds = subtitles[-1]["end"] if subtitles else 0.0

        # 写入 VTT 文件
        vtt_path = None
        if output_vtt:
            Path(output_vtt).parent.mkdir(parents=True, exist_ok=True)
            write_vtt(output_vtt, subtitles)
            vtt_path = output_vtt
            logger.info(f"✅ VTT 字幕已保存: {output_vtt}")

        # 写入 SRT 文件
        srt_path = None
        if output_srt:
            Path(output_srt).parent.mkdir(parents=True, exist_ok=True)
            write_srt(output_srt, subtitles)
            srt_path = output_srt
            logger.info(f"✅ SRT 字幕已保存: {output_srt}")

        return {
            "mp3": output_mp3,
            "vtt": vtt_path,
            "srt": srt_path,
            "subtitles": subtitles,
            "duration_seconds": round(duration_seconds, 2),
            "text_length": char_count,
            "voice": voice,
            "mp3_size_bytes": mp3_size,
        }


# ==================== 命令行入口 ====================

def main():
    parser = argparse.ArgumentParser(
        description="Edge-TTS 音频 + 字幕生成工具",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--input", type=str, help="输入文本文件路径")
    parser.add_argument("--text", type=str, help="直接输入要朗读的文本")
    parser.add_argument("--output", type=str, required=True, help="输出 MP3 文件路径")
    parser.add_argument("--vtt", type=str, help="输出 VTT 字幕文件路径（默认与 MP3 同目录）")
    parser.add_argument("--srt", type=str, help="输出 SRT 字幕文件路径")
    parser.add_argument("--voice", type=str, default="zh-CN-YunxiNeural", help="TTS 声音")
    parser.add_argument("--rate", type=str, default="-5%", help="语速调整")
    parser.add_argument("--pitch", type=str, default="-2Hz", help="音调调整")
    parser.add_argument("--json", type=str, help="将结果保存为 JSON 文件")

    args = parser.parse_args()

    # 读取文本
    if args.input:
        with open(args.input, 'r', encoding='utf-8') as f:
            text = f.read()
        logger.info(f"📄 从文件读取文本: {args.input} ({len(text)} 字)")
    elif args.text:
        text = args.text
    else:
        parser.error("请提供 --input 或 --text 参数")

    # 自动生成 VTT 路径
    vtt_path = args.vtt
    if not vtt_path and args.output:
        vtt_path = str(Path(args.output).with_suffix('.vtt'))

    # 生成
    gen = EdgeTTSGenerator()
    result = gen.generate(
        text=text,
        output_mp3=args.output,
        output_vtt=vtt_path,
        output_srt=args.srt,
        voice=args.voice,
        rate=args.rate,
        pitch=args.pitch,
    )

    # 输出结果
    print(f"\n{'═'*50}")
    print(f"🎉 生成完成！")
    print(f"{'═'*50}")
    print(f"  📄 音频: {result['mp3']} ({result['mp3_size_bytes'] / 1024:.1f} KB)")
    print(f"  ⏱️  时长: {result['duration_seconds']:.1f} 秒")
    print(f"  📝 字幕: {len(result['subtitles'])} 句")
    if result['vtt']:
        print(f"  📑 VTT:  {result['vtt']}")
    if result['srt']:
        print(f"  📑 SRT:  {result['srt']}")
    print(f"  🎙️  声音: {result['voice']}")

    # 保存 JSON
    if args.json:
        with open(args.json, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"  📋 JSON: {args.json}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    main()
