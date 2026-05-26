# 听书金句 - 部署指南

## 当前状态

### 已完成 ✅
1. 小程序代码开发完成（Phase 1-7 全部完成）
2. Phase 5 - 播放器已支持真实音频播放
3. 已生成 3 本书的 MP3 音频：
   - 小王子.mp3 (7.3MB)
   - 活着.mp3 (7.7MB)
   - 三体.mp3 (7.2MB)

### 待完成 ⚠️
1. 将 MP3 音频上传到微信云存储
2. 将 audioUrl 更新到云数据库

---

## 部署步骤

### 步骤 1：上传音频到云存储

在微信开发者工具中操作：

1. 打开 `D:\小程序开发\workbud_tingshu\miniprogram`
2. 点击「云开发」控制台 → 「云存储」
3. 点击「上传文件」，依次上传以下文件：
   - `pipeline/output/audios/小王子.mp3` → 记录文件 ID
   - `pipeline/output/audios/活着.mp3` → 记录文件 ID
   - `pipeline/output/audios/三体.mp3` → 记录文件 ID
4. 复制每个文件的「文件地址」(cloud://xxx.mp3)

### 步骤 2：更新数据并导入云数据库

方式 A - 使用云函数导入：
```javascript
// 在小程序管理页面的控制台执行
wx.cloud.callFunction({
  name: 'batchImportBooks',
  data: {
    action: 'import',
    data: [
      {
        title: '小王子',
        author: '安托万·德·圣-埃克苏佩里',
        category: 2,
        audioUrl: 'cloud://你的文件ID.mp3', // 替换为步骤1获取的真实ID
        // ... 其他字段
      },
      // ... 其他书籍
    ]
  }
})
```

方式 B - 手动在云开发控制台添加：
1. 打开「云开发」→「数据库」
2. 添加集合 `books`
3. 手动添加记录，填写 audioUrl 字段

### 步骤 3：测试播放

1. 在微信开发者工具中编译运行
2. 点击任意书籍进入详情页
3. 点击播放按钮，验证音频能否正常播放

---

## 生成更多音频

如需为其他书籍生成音频：

```bash
cd D:\小程序开发\workbud_tingshu\pipeline
python batch_generate_audio.py
```

生成的音频会保存在 `pipeline/output/audios/`

---

## 常见问题

### Q: 音频无法播放？
A: 检查 audioUrl 是否正确设置为云存储路径（cloud://xxx.mp3）

### Q: 如何添加更多书籍？
A: 修改 `data_source/step4_for_database_import.json`，然后运行 `python batch_generate_audio.py`

### Q: 数据库没有数据？
A: 运行 `python import_to_clouddb.py` 准备数据，然后使用云函数导入