// 云函数入口文件 - 微信登录
const cloud = require('wx-server-sdk')

cloud.init({
  env: cloud.DYNAMIC_CURRENT_ENV
})

const db = cloud.database()

// 云函数入口函数
exports.main = async (event, context) => {
  const { code } = event

  if (!code) {
    return {
      success: false,
      error: 'code不能为空'
    }
  }

  try {
    // 通过云开发环境获取用户信息
    // 注意：云开发环境下可直接获取已授权用户的openid
    const wx_context = cloud.getWXContext()
    
    // 如果云函数是被信任的云环境调用，可以直接获取openid
    const openid = wx_context.OPENID
    
    if (!openid) {
      return {
        success: false,
        error: '无法获取用户信息'
      }
    }

    // 查询或创建用户记录
    const usersCollection = db.collection('users')
    let userRes = await usersCollection.where({ openid }).get()
    
    let userInfo = null
    
    if (userRes.data.length > 0) {
      // 用户已存在，更新信息
      userInfo = userRes.data[0]
    } else {
      // 新用户，创建记录
      userInfo = {
        openid,
        nickname: '书友' + Math.floor(Math.random() * 10000),
        avatar: '',
        favoriteBooks: [],
        favoriteQuotes: [],
        playHistory: [],
        createTime: Date.now(),
        updateTime: Date.now()
      }
      await usersCollection.add({ data: userInfo })
    }

    return {
      success: true,
      data: {
        id: userInfo._id || userInfo.openid,
        openid: userInfo.openid,
        nickname: userInfo.nickname,
        avatar: userInfo.avatar
      }
    }
  } catch (err) {
    console.error('微信登录失败:', err)
    return {
      success: false,
      error: err.message
    }
  }
}