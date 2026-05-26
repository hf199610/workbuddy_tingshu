# 听书小程序 - 代码逻辑流程分析

## 一、系统整体架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           听书小程序系统架构                               │
└─────────────────────────────────────────────────────────────────────────────┘

┌──────────────────┐     ┌───────────────────┐     ┌──────────────────────┐
│   数据源层        │ ──▶ │   Pipeline处理层   │ ──▶ │   小程序展示层      │
│   (data_source/)  │     │   (pipeline/)     │     │   (miniprogram/)    │
└──────────────────┘     └───────────────────┘     └──────────────────────┘
        │                         │                          │
        ▼                         ▼                          ▼
  book_list_500.xlsx       书籍信息获取               云函数 getBooks
  crawled_books.json      MiniMax API 生成           pages/books 列表页
  books_sample_data.json  edge-tts 音频合成          pages/book-detail 详情页
  quotes_for_xxx.json    云数据库导入                utils/clouddb.js
                       字幕时间戳同步
```

## 二、数据流程详解

### 2.1 数据源层 (data_source/)

| 文件 | 用途 | 说明 |
|------|------|------|
| `book_list_500.xlsx` | 待处理书籍清单 | 500 本书，包含书名、作者、ISBN |
| `books_with_audio_url.json` | 未导入的书籍数据 | 包含基础信息和 MiniMax 生成的 script |
| `step4_for_database_import.json` | 待导入数据 | 完整字段，可以直接导入云数据库 |
| `quotes_for_database_import.json` | 名言警句数据 | 用于名言模块 |

### 2.2 Pipeline 处理层 (pipeline/)

| 脚本 | 功能 | 说明 |
|------|------|------|
| `crawl_books.py` | 采集书籍信息 | 豆瓣爬虫，获取基础信息 |
| `generate_scripts.py` | 生成讲解文稿 | 基于书籍信息生成简介、讲解稿 |
| `generate_subtitles.py` | 生成分句字幕 | 将长文本拆分为 sentences 数组 |
| `edge_tts_generator.py` | TTS 音频合成 | edge-tts 免费服务 |
| `batch_update.py` | 批量更新 | 补充音频时长等信息 |
| `cloud_import_only.py` | 云数据库导入 | HTTP API 方式导入 |

### 2.3 小程序展示层 (miniprogram/)

| 模块 | 文件 | 功能 |
|------|------|------|
| **云函数** | `cloudfunctions/getBooks/` | 获取书籍列表 |
| **云函数** | `cloudfunctions/getBookDetail/` | 获取书籍详情 |
| **云函数** | `cloudfunctions/batchImportBooks/` | 批量导入 |
| **工具** | `utils/clouddb.js` | 云数据库 API 封装 |
| **页面** | `pages/books/` | 书籍列表页 |
| **页面** | `pages/book-detail/` | 书籍详情页 |

## 三、核心数据模型

### Books 集合字段

```javascript
{
  // ========== 基础信息 ==========
  id: String,              // 书籍ID（云数据库自动生成_id）
  title: String,           // 书名
  author: String,          // 作者
  
  // ========== 分类信息 ==========
  category: Number,       // 分类ID (1-12)
  categoryName: String,    // 分类名称
  
  // ========== 封面信息（重点）==========
  coverColor: String,     // 封面背景色，如 "#8B4513"
  coverUrl: String,       // 封面图片URL（可选，无图时用 coverColor）
  
  // ========== 字幕/音频（核心）==========
  script: String,        // 完整讲解稿 (~4500字)
  scriptLength: Number,   // 字数
  sentences: Array,       // 分句数组 [{text, startTime, endTime}]
  
  audioUrl: String,       // 音频文件URL（云存储）
  audioDuration: Number, // 音频时长（秒）
  audioDurationText: String, // "约18分钟"
  isAudioGenerated: Boolean, // 是否已生成音频
  
  // ========== 状态 ==========
  isHot: Boolean,       // 热门推荐
  isGenerated: Boolean,  // 已完成生成
  isPublished: Boolean, // 已发布
  
  // ========== 时间戳 ==========
  createTime: Number,
  updateTime: Number
}
```

### 分类ID对照表

| ID | 分类名 | 默认颜色 |
|----|--------|----------|
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

## 四、当前问题分析

### 问题1：数据源自动化

**现状**：
- 需要手动运行各个 Pipeline 脚本
- 没有实现全自动化的调度

**解决方向**：
- 编写自动化调度脚本
- 实现定时任务
- 监控处理进度，处理异常

**待处理步骤**：
1. 从 `book_list_500.xlsx` 读取待处理书籍
2. 调用 talelin API 获取基础信息
3. 调用 MiniMax API 生成讲解稿
4. edge-tts 生成音频
5. 计算字幕时间戳
6. 导入云数据库

### 问题2：封面展示

**现状**：
- 数据有 `coverColor` 和 `coverUrl` 两个字段
- 代码使用 `color` 字段，可能存在字段名不匹配

**解决方向**：
- 统一字段名称：小程序读取时转换 `coverColor` → `color`
- 获取真实的豆瓣封面图 URL
- 优化色彩方案

**代码检查点**：
```
pages/books/books.js         读取 .color
pages/books/books.wxml      显示 item.color
cloudfunctions/getBooks   返回 coverColor (需确认)
```

## 五、执行命令参考

### 本地测试 Pipeline

```bash
cd pipeline

# 测试单本书处理
python full_pipeline.py --book "活着"

# 测试批量处理
python full_pipeline.py --count 5

# 导入云数据库
python cloud_import_only.py --check   # 检查
python cloud_import_only.py          # 导入
```

### 部署云函数

```bash
# 在微信开发者工具中
# 上传并部署：cloudfunctions/*
```

## 六、下一步工作重点

1. **数据源自动化**
   - [ ] 完善 full_pipeline.py 的异常处理
   - [ ] 添加重试机制
   - [ ] 实现断点续传（记录已处理书籍）

2. **封面展示优化**
   - [ ] 统一字段名（coverColor ↔ color）
   - [ ] 添加真实封面图获取
   - [ ] 优化封面色彩

3. **云数据库管理**
   - [ ] 去重逻辑
   - [ ] 书籍数量控制
   - [ ] 增量更新