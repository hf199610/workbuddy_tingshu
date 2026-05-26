#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
清空数据库 quotes 集合下的所有数据
使用方式：
  python clear_quotes_collection.py --dry-run   # 预览
  python clear_quotes_collection.py             # 执行删除
"""

import os
import json
import logging
import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def load_env():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    for env_path in [os.path.join(script_dir, '.env'), os.path.join(script_dir, '..', '.env')]:
        if os.path.exists(env_path):
            with open(env_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        os.environ.setdefault(key.strip(), value.strip())


def get_access_token():
    app_id = os.environ.get("WECHAT_APP_ID")
    secret = os.environ.get("WECHAT_SECRET")
    url = f"https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={app_id}&secret={secret}"
    resp = httpx.get(url, timeout=30)
    data = resp.json()
    if "access_token" not in data:
        raise Exception(f"获取 token 失败: {data}")
    return data["access_token"]


def count_quotes(access_token, env_id):
    """统计 quotes 集合总数"""
    url = f"https://api.weixin.qq.com/tcb/databasecount?access_token={access_token}"
    resp = httpx.post(url, json={
        "env": env_id,
        "query": 'db.collection("quotes").count()'
    }, timeout=30)
    result = resp.json()
    if result.get("errcode") != 0:
        logger.warning(f"统计数量失败: {result}")
        return -1
    return result.get("pager", {}).get("Total", -1)


def query_ids(access_token, env_id, limit=100):
    """查询 quotes 集合的文档 _id，每次查前 limit 条（删完再查，不会漏）"""
    url = f"https://api.weixin.qq.com/tcb/databasequery?access_token={access_token}"
    resp = httpx.post(url, json={
        "env": env_id,
        "query": f'db.collection("quotes").limit({limit}).field("_id").get()'
    }, timeout=30)
    result = resp.json()
    if result.get("errcode") != 0:
        raise Exception(f"查询 _id 失败: {result}")
    ids = []
    for item in result.get("data", []):
        try:
            ids.append(json.loads(item).get("_id"))
        except Exception:
            pass
    return ids


def delete_by_id(access_token, env_id, doc_id):
    """通过 _id 删除单条文档"""
    url = f"https://api.weixin.qq.com/tcb/databasedelete?access_token={access_token}"
    resp = httpx.post(url, json={
        "env": env_id,
        "query": f'db.collection("quotes").doc("{doc_id}").remove()'
    }, timeout=30)
    return resp.json()


def clear_all_quotes(access_token, env_id, dry_run=False):
    """清空 quotes 集合 —— 循环查前100条 ID、逐条删除，直到集合为空"""
    total = count_quotes(access_token, env_id)
    logger.info(f"quotes 集合当前共 {total} 条记录")

    if dry_run:
        logger.info("[DRY RUN] 预览模式，不执行删除")
        ids = query_ids(access_token, env_id, limit=5)
        for did in ids:
            logger.info(f"  将删除 _id: {did}")
        return

    batch_num = 0
    deleted_total = 0
    failed_total = 0

    while True:
        ids = query_ids(access_token, env_id, limit=100)
        if not ids:
            logger.info("查询结果为空，删除完成")
            break

        batch_num += 1
        batch_deleted = 0
        batch_failed = 0

        for did in ids:
            result = delete_by_id(access_token, env_id, did)
            if result.get("errcode") == 0:
                batch_deleted += 1
            else:
                batch_failed += 1
                logger.warning(f"  删除失败 _id={did}: {result}")

        deleted_total += batch_deleted
        failed_total += batch_failed
        logger.info(f"第 {batch_num} 批: 成功 {batch_deleted} 条, 失败 {batch_failed} 条, 累计删除 {deleted_total} 条")

        # 本批不足100条说明已经全部处理完
        if len(ids) < 100:
            break

    logger.info(f"\n{'='*50}")
    logger.info(f"quotes 集合清空完成!")
    logger.info(f"  成功删除: {deleted_total} 条")
    logger.info(f"  失败: {failed_total} 条")
    logger.info(f"{'='*50}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description='清空数据库 quotes 集合')
    parser.add_argument('--dry-run', action='store_true', help='仅预览，不执行删除')
    args = parser.parse_args()

    load_env()

    app_id = os.environ.get("WECHAT_APP_ID")
    secret = os.environ.get("WECHAT_SECRET")
    env_id = os.environ.get("WECHAT_ENV_ID")

    if not all([app_id, secret, env_id]):
        logger.error("缺少必要的环境变量，请检查 .env 文件")
        return

    if not args.dry_run:
        confirm = input("⚠️ 即将删除 quotes 集合中的所有数据！此操作不可逆！\n确认执行? (yes/no): ")
        if confirm.lower() != 'yes':
            logger.info("已取消")
            return

    access_token = get_access_token()
    logger.info("Token 获取成功")

    clear_all_quotes(access_token, env_id, dry_run=args.dry_run)


if __name__ == "__main__":
    main()