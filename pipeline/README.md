# 听书内容自动化生产流水线

## 目录结构
```
pipeline/
├── config.yaml          # 配置文件（API密钥等）
├── requirements.txt     # Python依赖
├── main.py              # 主程序入口
├── book_list.txt        # 书名列表
├── output/              # 输出目录
│   ├── data/           # JSON数据包
│   ├── covers/         # 封面图
│   ├── scripts/        # 文稿文本
│   └── audios/         # 音频文件
├── logs/               # 日志目录
└── modules/
    ├── __init__.py
    ├── config_loader.py    # 配置加载
    ├── book_info.py       # 图书数据获取
    ├── content_gen.py     # AI文稿生成
    ├── tts_synth.py       # TTS音频合成
    ├── data_storage.py    # JSON存储
    └── pipeline.py        # 流水线调度
```

## 环境准备
```bash
pip install -r requirements.txt
```

## 运行
```bash
python main.py
```

## 依赖
- Python 3.8+
- volcenginesdkarkruntime (豆包API)
- volcengine-python-sdk (火山引擎TTS)
- pyyaml (配置管理)
- requests (HTTP请求)
