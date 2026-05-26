# Books集合 - 完整字段设计

## 集合名称
`books`

## 字段设计

```javascript
{
  // ========== 基础信息（必填）==========
  title: String,           // 书名 - 必填
  author: String,          // 作者 - 必填
  
  // ========== 分类信息 ==========
  category: Number,        // 分类ID (1-12)
  categoryName: String,    // 分类名称
  
  // ========== 出版信息 ==========
  publisher: String,      // 出版社
  isbn: String,           // ISBN
  publishDate: String,    // 出版日期
  pages: Number,          // 页数
  
  // ========== 描述信息 ==========
  description: String,    // 书籍简介
  coverColor: String,     // 封面背景色（无封面图时使用）
  coverUrl: String,       // 封面图片URL（可选）
  
  // ========== 字幕/文稿（核心字段）==========
  script: String,         // 完整字幕/文稿（约4500字）
  scriptLength: Number,   // 字幕字数
  scriptSource: String,   // 文稿来源：api生成的 / 手动编辑的 / 爬取的
  scriptVersion: Number,  // 文稿版本号
  
  // 字幕分句（用于字幕同步播放）
  sentences: Array,       // 分句数组
  /*
  sentences格式：
  [
    { text: "第一句", startTime: 0, endTime: 3.5, audioFile: "chunk_001.mp3" },
    { text: "第二句", startTime: 3.5, endTime: 7.2, audioFile: "chunk_002.mp3" },
    ...
  ]
  */
  
  // ========== 音频信息 ==========
  audioUrl: String,       // 音频文件URL（云存储地址）
  audioDuration: Number,  // 音频总时长（秒）
  audioDurationText: String, // 音频时长文本 "约18分钟"
  audioFileId: String,    // 云存储文件ID
  isAudioGenerated: Boolean, // 是否已生成音频
  
  // TTS参数
  ttsVoice: String,       // 使用的音色：YunxiNeural（男声） / XiaoxiaoNeural（女声）
  ttsRate: String,        // 语速："-10%"（沉稳）
  ttsPitch: String,      // 音调："-5Hz"
  
  // ========== 状态标记 ==========
  isHot: Boolean,        // 是否热门
  isGenerated: Boolean,   // 是否已完成生成（字幕+音频）
  isPublished: Boolean,   // 是否已发布
  viewCount: Number,      // 浏览次数
  playCount: Number,      // 播放次数
  
  // ========== 质量管理 ==========
  qualityScore: Number,   // 质量评分（1-10）
  qualityNote: String,    // 质量备注
  
  // ========== 时间戳 ==========
  createTime: Number,     // 创建时间戳
  updateTime: Number,     // 更新时间戳
  
  // ========== 来源追溯 ==========
  source: String,         // 数据来源：crawl（爬虫）/ manual（手动）/ import（导入）
  sourceUrl: String,      // 原始来源URL
  crawlTime: Number,      // 爬取时间
  importedBooks: String    // 爬取批次标识
}
```

## 存储空间估算

| 字段类型 | 单本书占用 |
|---------|-----------|
| 基础信息 | ~2 KB |
| 描述简介 | ~1 KB |
| 字幕正文(4500字) | ~13.5 KB |
| 分句数组(JSON) | ~5 KB |
| 音频URL等 | ~0.5 KB |
| **合计** | **~22 KB/书** |

**1000本书 ≈ 22 MB** ✅ 微信云数据库完全足够

## 索引设计（云数据库）

建议在云开发控制台创建以下索引：

1. `category` - 按分类查询
2. `isHot` - 查询热门书籍
3. `createTime` - 按时间排序
4. `updateTime` - 按更新时间排序
5. `title` - 全文索引（搜索）

## 分类ID对照表

| ID | 分类名 | 颜色 |
|----|--------|------|
| 1 | 经典名著 | #8B4513 |
| 2 | 儿童文学 | #FF6B6B |
| 3 | 科普百科 | #4ECDC4 |
| 4 | 历史传记 | #9B59B6 |
| 5 | 哲学心理 | #3498DB |
| 6 | 文学小说 | #E74C3C |
| 7 | 诗词歌赋 | #F39C12 |
| 8 | 家庭教育 | #27AE60 |
| 9 | 成长励志 | #1ABC9C |
| 10 | 科幻悬疑 | #2C3E50 |
| 11 | 散文随笔 | #E67E22 |
| 12 | 其他 | #95A5A6 |

## 示例数据

```json
{
  "title": "小王子",
  "author": "安托万·德·圣-埃克苏佩里",
  "category": 2,
  "categoryName": "儿童文学",
  "publisher": "人民文学出版社",
  "isbn": "978-7-0200-0987-8",
  "description": "这是一本足以让人永葆童心的不朽经典...",
  "coverColor": "#FFE4C4",
  "script": "各位听众朋友好，欢迎收听今天的节目...",
  "scriptLength": 4500,
  "scriptSource": "api生成",
  "sentences": [
    { "text": "各位听众朋友好，欢迎收听今天的节目。", "startTime": 0, "endTime": 3.5 },
    { "text": "今天我要为大家分享的是法国作家圣埃克苏佩里的经典作品《小王子》。", "startTime": 3.5, "endTime": 8.2 }
  ],
  "audioUrl": "",
  "audioDuration": 1080,
  "audioDurationText": "约18分钟",
  "isAudioGenerated": false,
  "ttsVoice": "YunxiNeural",
  "ttsRate": "-10%",
  "ttsPitch": "-5Hz",
  "isHot": true,
  "isGenerated": false,
  "isPublished": false,
  "viewCount": 0,
  "playCount": 0,
  "qualityScore": 0,
  "qualityNote": "",
  "createTime": 1640000000000,
  "updateTime": 1640000000000,
  "source": "crawl",
  "sourceUrl": "https://book.douban.com/subject/1007308/",
  "crawlTime": 1640000000000,
  "importedBooks": "batch_001"
}
```
