// 云函数入口文件
const cloud = require('wx-server-sdk')

cloud.init({
  env: cloud.DYNAMIC_CURRENT_ENV
})

const db = cloud.database()

// 云函数入口函数
exports.main = async (event, context) => {
  const { categoryId = 0, limit = 20, skip = 0 } = event

  try {
    let query = db.collection('books')

    // 分类筛选
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
