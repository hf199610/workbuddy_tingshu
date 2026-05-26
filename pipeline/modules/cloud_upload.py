"""
微信云存储文件上传模块
将本地文件（音频、字幕等）上传到微信云开发存储空间。

使用方法:
  from modules.cloud_upload import CloudStorageUploader

  uploader = CloudStorageUploader()
  result = uploader.upload_file(
      file_path="output/audios/活着.mp3",
      cloud_path="audios/活着.mp3"
  )
  # result = { "fileID": "cloud://xxx", "media_id": "xxx", "url": "https://xxx" }
"""

import os
import json
import logging
from typing import Optional, Dict
from pathlib import Path

logger = logging.getLogger(__name__)


class CloudStorageUploader:
    """微信云存储文件上传器"""

    def __init__(self, app_id: str = None, secret: str = None, env_id: str = None):
        self.app_id = app_id or os.getenv("WECHAT_APP_ID", "")
        self.secret = secret or os.getenv("WECHAT_SECRET", "")
        self.env_id = env_id or os.getenv("WECHAT_ENV_ID", "cloud1-d2ggs9k1bf3aa2a18")
        self.access_token = None

        if not self.app_id or not self.secret:
            logger.warning("未配置 WECHAT_APP_ID / WECHAT_SECRET，无法上传文件")

    def get_access_token(self) -> Optional[str]:
        """获取微信 access_token"""
        import httpx

        if self.access_token:
            return self.access_token

        url = "https://api.weixin.qq.com/cgi-bin/token"
        params = {
            "grant_type": "client_credential",
            "appid": self.app_id,
            "secret": self.secret,
        }

        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.get(url, params=params)
                result = response.json()

                if "access_token" in result:
                    self.access_token = result["access_token"]
                    logger.info("access_token 获取成功")
                    return self.access_token
                else:
                    logger.error(f"获取 access_token 失败: {result}")
                    return None
        except Exception as e:
            logger.error(f"获取 access_token 异常: {e}")
            return None

    def upload_file(self, file_path: str, cloud_path: str) -> Dict:
        """
        上传文件到微信云存储。

        Args:
            file_path: 本地文件路径
            cloud_path: 云存储路径（如 "audios/活着.mp3"）

        Returns:
            dict: { "fileID": str, "url": str } 或 { "error": str }
        """
        import httpx

        file_path = Path(file_path)
        if not file_path.exists():
            return {"error": f"文件不存在: {file_path}"}

        if not self.get_access_token():
            return {"error": "无法获取 access_token"}

        file_size = file_path.stat().st_size
        logger.info(f"📤 上传文件: {file_path.name} ({file_size / 1024:.1f} KB) → {cloud_path}")

        try:
            with httpx.Client(timeout=120.0) as client:
                # Step 1: 获取上传 URL 和 token
                step1_url = "https://api.weixin.qq.com/tcb/uploadfile"
                step1_params = {"access_token": self.access_token}
                step1_data = {
                    "env": self.env_id,
                    "path": cloud_path,
                }

                resp1 = client.post(step1_url, params=step1_params, json=step1_data)
                result1 = resp1.json()

                if "url" not in result1:
                    logger.error(f"获取上传 URL 失败: {result1}")
                    return {"error": f"获取上传URL失败: {result1}"}

                upload_url = result1["url"]
                token = result1["token"]
                authorization = result1["authorization"]
                file_id = result1["file_id"]
                cos_upload_id = result1["cos_upload_id"]

                # Step 2: 上传文件到 COS
                with open(file_path, "rb") as f:
                    file_data = f.read()

                # 使用 multipart/form-data 格式
                step2_headers = {
                    "Authorization": authorization,
                }
                step2_files = {
                    "key": (None, cloud_path),
                    "Signature": (None, token),
                    "x-cos-security-token": (None, token),
                    "x-cos-meta-fileid": (None, file_id),
                    "file": (file_path.name, file_data, "application/octet-stream"),
                }

                resp2 = client.post(upload_url, headers=step2_headers, files=step2_files)

                if resp2.status_code == 204:
                    logger.info(f"✅ 上传成功: fileID = {file_id}")
                    return {
                        "fileID": file_id,
                        "url": f"https://tcb.tencentcloudapi.com/web?env={self.env_id}&fileId={file_id}",
                        "size": file_size,
                    }
                else:
                    logger.error(f"上传失败: status={resp2.status_code}, body={resp2.text}")
                    return {"error": f"上传失败: HTTP {resp2.status_code}"}

        except Exception as e:
            logger.error(f"上传异常: {e}")
            return {"error": str(e)}

    def upload_book_assets(
        self,
        book_title: str,
        mp3_path: str = None,
        vtt_path: str = None,
    ) -> Dict:
        """
        上传一本书的所有资源文件（音频 + 字幕）。

        Args:
            book_title: 书名（用于云存储路径）
            mp3_path: MP3 文件路径
            vtt_path: VTT 字幕文件路径

        Returns:
            dict: {
                "audioUrl": str,    # 云存储 fileID
                "subtitleUrl": str, # 云存储 fileID
            }
        """
        results = {}

        if mp3_path and Path(mp3_path).exists():
            mp3_result = self.upload_file(mp3_path, f"audios/{book_title}.mp3")
            if "fileID" in mp3_result:
                results["audioUrl"] = mp3_result["fileID"]
            else:
                logger.error(f"MP3 上传失败: {mp3_result.get('error')}")
                results["audioUrl"] = ""

        if vtt_path and Path(vtt_path).exists():
            vtt_result = self.upload_file(vtt_path, f"subtitles/{book_title}.vtt")
            if "fileID" in vtt_result:
                results["subtitleUrl"] = vtt_result["fileID"]
            else:
                logger.error(f"VTT 上传失败: {vtt_result.get('error')}")
                results["subtitleUrl"] = ""

        return results

    def update_book_audio_fields(self, book_title: str, audio_url: str, subtitle_url: str,
                                  subtitles_json: list = None, audio_duration: float = 0) -> Dict:
        """
        更新云数据库中书籍的音频相关字段。

        Args:
            book_title: 书名（用于查找）
            audio_url: 音频云存储 fileID
            subtitle_url: 字幕云存储 fileID
            subtitles_json: 字幕 JSON 数组
            audio_duration: 音频时长（秒）

        Returns:
            dict: 更新结果
        """
        import httpx

        if not self.get_access_token():
            return {"success": False, "error": "无法获取 access_token"}

        # 构建更新数据
        update_fields = {
            "audioUrl": audio_url,
            "subtitleUrl": subtitle_url,
            "isAudioGenerated": True,
            "updateTime": int(__import__('time').time() * 1000),
        }

        if audio_duration > 0:
            update_fields["audioDuration"] = audio_duration
            mins = int(audio_duration // 60)
            secs = int(audio_duration % 60)
            update_fields["audioDurationText"] = f"{mins:02d}:{secs:02d}"

        # 注意：微信云数据库 HTTP API 的 update 需要用 doc().update()
        # 但由于我们可能不知道文档 _id，需要先查询
        # 这里使用 where + update 的方式

        # 先查询 _id
        query_url = "https://api.weixin.qq.com/tcb/databasequery"
        params = {"access_token": self.access_token}
        safe_title = book_title.replace("'", "\\'")
        query = f"db.collection('books').where({{title: '{safe_title}'}}).limit(1).get()"

        try:
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(query_url, params=params, json={"env": self.env_id, "query": query})
                result = resp.json()

                if result.get("errcode") != 0 or not result.get("data"):
                    return {"success": False, "error": f"未找到书籍: {book_title}"}

                records = result["data"]
                if isinstance(records, str):
                    records = json.loads(records)

                if not records:
                    return {"success": False, "error": f"未找到书籍记录: {book_title}"}

                doc_id = records[0].get("_id", "")
                if not doc_id:
                    return {"success": False, "error": "记录缺少 _id 字段"}

                logger.info(f"找到书籍记录: _id = {doc_id}")

        except Exception as e:
            return {"success": False, "error": f"查询异常: {e}"}

        # 更新记录（包含 subtitles 数据）
        if subtitles_json:
            update_fields["subtitles"] = subtitles_json

        # 构建 update query
        update_data = json.dumps(update_fields, ensure_ascii=False)
        update_query = f'db.collection(\'books\').doc(\'{doc_id}\').update({{data: {update_data}}})'

        update_url = "https://api.weixin.qq.com/tcb/databaseupdate"
        try:
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(update_url, params=params, json={"env": self.env_id, "query": update_query})
                result = resp.json()

                if result.get("errcode") == 0:
                    updated = result.get("updated", 0)
                    logger.info(f"✅ 书籍音频字段更新成功: {book_title} ({updated} 条)")
                    return {"success": True, "updated": updated}
                else:
                    logger.error(f"更新失败: {result}")
                    return {"success": False, "error": str(result)}

        except Exception as e:
            return {"success": False, "error": str(e)}
