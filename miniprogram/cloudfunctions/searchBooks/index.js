// 云函数入口文件
const cloud = require('wx-server-sdk')

cloud.init({
  env: cloud.DYNAMIC_CURRENT_ENV
})

const db = cloud.database()

// 云函数入口函数
exports.main = async (event, context) => {
  const { keyword } = event

  if (!keyword) {
    return {
      success: true,
      data: []
    }
  }

  try {
    // 使用正则表达式进行模糊搜索（搜索标题和作者）
    const res = await db.collection('books')
      .where(db.command.or([
        {
          title: db.RegExp({
            regexp: keyword,
            options: 'i' // 不区分大小写
          })
        },
        {
          author: db.RegExp({
            regexp: keyword,
            options: 'i'
          })
        }
      ]))
      .get()

    return {
      success: true,
      data: res.data
    }
  } catch (err) {
    return {
      success: false,
      error: err.message,
      data: []
    }
  }
}
