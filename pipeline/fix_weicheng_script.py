#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""修复围城讲解稿"""

import os
import httpx
import json
from anthropic import Anthropic

# 加载环境变量
for line in open('.env', 'r', encoding='utf-8'):
    line = line.strip()
    if line and not line.startswith('#') and '=' in line:
        k, v = line.split('=', 1)
        os.environ[k.strip()] = v.strip()

app_id = os.environ.get('WECHAT_APP_ID')
secret = os.environ.get('WECHAT_SECRET')
env_id = os.environ.get('WECHAT_ENV_ID')

print('=== Step 1: 生成围城讲解稿 ===')
client = Anthropic(
    api_key=os.environ.get('ANTHROPIC_API_KEY'),
    base_url=os.environ.get('ANTHROPIC_BASE_URL', 'https://api.minimaxi.com/anthropic'),
)

print('调用MiniMax API...')
msg = client.messages.create(
    model=os.environ.get('MINIMAX_MODEL', 'MiniMax-M2.7'),
    max_tokens=8000,
    messages=[{
        'role': 'user',
        'content': '请为《围城》生成一段4200字左右的书籍讲解稿。围城是钱钟书先生的经典长篇小说，描写了知识分子在婚姻、事业中的困境。语言通俗易懂，适合听书场景。只输出讲解稿内容。'
    }],
)

script = ''
for block in msg.content:
    if hasattr(block, 'type') and block.type == 'text' and hasattr(block, 'text'):
        script = block.text.strip()
        print(f'找到文本块: {len(script)} 字')
        break

if not script:
    print('ERROR: 未找到文本内容')
    print('Raw content:', msg.content)
    exit(1)

print(f'讲解稿长度: {len(script)} 字')
print(f'预览: {script[:150]}...')

# 保存到本地
os.makedirs('output/data', exist_ok=True)
with open('output/data/围城_script.txt', 'w', encoding='utf-8') as f:
    f.write(script)
print('已保存到 output/data/围城_script.txt')

# 更新数据库
print('\n=== Step 2: 更新云数据库 ===')

def escape_str(s):
    s = str(s)
    s = s.replace("\\", "\\\\")
    s = s.replace('"', '\\"')
    s = s.replace("\n", " ")
    s = s.replace("\r", " ")
    s = s.replace("\t", " ")
    return s

# 获取token
resp = httpx.get(f'https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={app_id}&secret={secret}', timeout=30)
token = resp.json().get('access_token')
print(f'Token: {token[:20]}...')

# 更新数据
update_data = {
    'script': escape_str(script[:500]),  # 只存前500字预览
    'scriptLength': len(script)
}
data_str = json.dumps(update_data, ensure_ascii=False)
query = f'db.collection("books").where({{"title":"围城"}}).update({{data: {data_str}}})'

url = f'https://api.weixin.qq.com/tcb/databaseupdate?access_token={token}'
r = httpx.post(url, json={'env': env_id, 'query': query}, timeout=30)
result = r.json()
print(f'更新结果: {result}')

if result.get('errcode') == 0:
    print('✓ 围城讲解稿修复成功!')
else:
    print(f'✗ 更新失败: {result}')
