"""
配置加载模块
从 config.yaml 加载所有配置
"""
import os
import yaml

class Config:
    _instance = None
    _config = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_config()
        return cls._instance

    def _load_config(self):
        """加载配置文件"""
        config_path = os.path.join(os.path.dirname(__file__), "..", "config.yaml")
        with open(config_path, "r", encoding="utf-8") as f:
            self._config = yaml.safe_load(f)

    @property
    def aliyun(self):
        return self._config.get("aliyun", {})

    @property
    def doubao(self):
        return self._config.get("doubao", {})

    @property
    def tts(self):
        return self._config.get("tts", {})

    @property
    def pipeline(self):
        return self._config.get("pipeline", {})

    @property
    def test_books(self):
        return self._config.get("test_books", [])

    def is_test_mode(self):
        return self.pipeline.get("test_mode", True)


def get_config():
    return Config()
