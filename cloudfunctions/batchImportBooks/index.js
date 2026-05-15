// 云函数入口文件 - 批量导入书籍
const cloud = require('wx-server-sdk')

cloud.init({
  env: cloud.DYNAMIC_CURRENT_ENV
})

const db = cloud.database()
const _ = db.command

// 云函数入口函数
exports.main = async (event, context) => {
  const { action = 'import', data = [] } = event

  try {
    if (action === 'import') {
      return await batchImportBooks(data)
    } else if (action === 'getCategories') {
      return getCategories()
    } else if (action === 'getBooks') {
      return await getBooks(event)
    } else {
      return {
        success: false,
        error: '未知操作',
        data: []
      }
    }
  } catch (err) {
    return {
      success: false,
      error: err.message,
      data: []
    }
  }
}

// 批量导入书籍
async function batchImportBooks(books) {
  if (!books || books.length === 0) {
    return {
      success: false,
      error: '没有数据可导入',
      data: { imported: 0 }
    }
  }

  const now = Date.now()
  let successCount = 0
  let errorCount = 0
  const errors = []

  // 逐条导入（微信云开发批量add有500条限制）
  for (const book of books) {
    try {
      // 补充必要字段
      const bookData = {
        ...book,
        createTime: book.createTime || now,
        updateTime: book.updateTime || now,
        isHot: book.isHot || false,
        audioUrl: book.audioUrl || '',
        scriptUrl: book.scriptUrl || '',
        coverColor: book.coverColor || '#FFE4C4'
      }

      await db.collection('books').add({
        data: bookData
      })
      successCount++
    } catch (err) {
      errorCount++
      errors.push({
        title: book.title,
        error: err.message
      })
    }
  }

  return {
    success: true,
    data: {
      imported: successCount,
      failed: errorCount,
      errors: errors.slice(0, 10) // 最多返回10个错误
    }
  }
}

// 获取分类列表
function getCategories() {
  const categories = [
    { id: 1, name: '经典名著', color: '#8B4513' },
    { id: 2, name: '儿童文学', color: '#FF6B6B' },
    { id: 3, name: '科普百科', color: '#4ECDC4' },
    { id: 4, name: '历史传记', color: '#9B59B6' },
    { id: 5, name: '哲学心理', color: '#3498DB' },
    { id: 6, name: '文学小说', color: '#E74C3C' },
    { id: 7, name: '诗词歌赋', color: '#F39C12' },
    { id: 8, name: '家庭教育', color: '#27AE60' },
    { id: 9, name: '成长励志', color: '#1ABC9C' },
    { id: 10, name: '科幻悬疑', color: '#2C3E50' },
    { id: 11, name: '散文随笔', color: '#E67E22' },
    { id: 12, name: '其他', color: '#95A5A6' }
  ]

  return {
    success: true,
    data: categories
  }
}

// 获取书籍列表（支持分类筛选）
async function getBooks(event) {
  const { categoryId = 0, limit = 20, skip = 0 } = event

  try {
    let query = db.collection('books')

    if (categoryId > 0) {
      query = query.where({ category: categoryId })
    }

    const res = await query
      .orderBy('updateTime', 'desc')
      .limit(limit)
      .skip(skip)
      .get()

    return {
      success: true,
      data: res.data,
      total: res.data.length
    }
  } catch (err) {
    return {
      success: false,
      error: err.message,
      data: []
    }
  }
}
