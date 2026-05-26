"""
听书内容自动化生产流水线 - 主程序
一键运行：图书数据获取 → AI文稿生成 → TTS音频合成
"""
import sys
import os

# 确保 modules 可以被导入
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from modules.pipeline import Pipeline


def main():
    print("""
╔══════════════════════════════════════════════════════╗
║       听书内容自动化生产流水线 v1.0                   ║
║       图书数据 → AI文稿 → TTS音频 → 数据包          ║
╚══════════════════════════════════════════════════════╝
    """)

    # 创建并运行流水线
    pipeline = Pipeline()
    pipeline.run()

    print("\n✅ 流水线执行完成！")


if __name__ == "__main__":
    main()
