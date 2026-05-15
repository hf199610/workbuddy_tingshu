// 云函数入口文件
const cloud = require('wx-server-sdk')

cloud.init({
  env: cloud.DYNAMIC_CURRENT_ENV
})

const db = cloud.database()
const _ = db.command

// 云函数入口函数
exports.main = async (event, context) => {
  const { filter = 'all', bookId = null, limit = 20, skip = 0 } = event

  try {
    let query = db.collection('quotes')

    // 书籍筛选
    if (bookId) {
      query = query.where({ bookId })
    }

    let res
    if (filter === 'hot') {
      res = await query
        .orderBy('playCount', 'desc')
        .limit(limit)
        .skip(skip)
        .get()
    } else if (filter === 'liked') {
      res = await query
        .where({ playCount: _.gte(1000) })
        .orderBy('playCount', 'desc')
        .limit(limit)
        .skip(skip)
        .get()
    } else {
      res = await query
        .orderBy('createTime', 'desc')
        .limit(limit)
        .skip(skip)
        .get()
    }

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
