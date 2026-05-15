// 云函数入口文件
const cloud = require('wx-server-sdk')

cloud.init({
  env: cloud.DYNAMIC_CURRENT_ENV
})

const db = cloud.database()

// 云函数入口函数
exports.main = async (event, context) => {
  const { bookId } = event

  if (!bookId) {
    return {
      success: false,
      error: '缺少书籍ID',
      data: null
    }
  }

  try {
    const res = await db.collection('books')
      .doc(bookId)
      .get()

    if (res.data) {
      return {
        success: true,
        data: res.data
      }
    } else {
      return {
        success: false,
        error: '书籍不存在',
        data: null
      }
    }
  } catch (err) {
    return {
      success: false,
      error: err.message,
      data: null
    }
  }
}
