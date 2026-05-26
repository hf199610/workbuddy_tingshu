// 云函数入口文件
const cloud = require('wx-server-sdk')

cloud.init({
  env: cloud.DYNAMIC_CURRENT_ENV
})

const db = cloud.database()

// 数字ID到分类名称的映射（与constants.js保持一致）
const CATEGORY_MAP = {
  0: '',  // 全部
  1: '经典名著',
  2: '儿童文学',
  3: '文学小说',
  4: '诗词歌赋',
  5: '哲学心理',
  6: '科普百科',
  7: '历史传记',
  8: '科幻悬疑',
  9: '成长励志',
  10: '散文随笔',
  11: '家庭教育',
}

// 云函数入口函数
exports.main = async (event, context) => {
  const { categoryId = 0, limit = 20, skip = 0 } = event

  try {
    let query = db.collection('books')

    // 分类筛选（categoryId=0表示全部，不加筛选条件）
    if (categoryId > 0) {
      const categoryName = CATEGORY_MAP[categoryId]
      if (categoryName) {
        query = query.where({ category: categoryName })
      }
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
