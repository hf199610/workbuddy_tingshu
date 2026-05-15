// clouddb.js - 微信云开发数据库封装（增强版）
const app = getApp()

/**
 * 云开发数据库工具类
 * 提供统一的数据库和云函数调用接口
 * 支持直接调用云函数进行复杂查询
 */
class CloudDB {
  constructor() {
    this.db = null
    this.useCloudFunction = true // 优先使用云函数
    this.init()
  }

  // 初始化云数据库
  init() {
    if (!wx.cloud) {
      console.warn('当前环境不支持云开发')
      this.useCloudFunction = false
      return
    }

    // 初始化云开发
    wx.cloud.init({
      env: app.globalData.cloudEnv || cloud.DYNAMIC_CURRENT_ENV,
      traceUser: true
    })

    this.db = wx.cloud.database()
  }

  // 获取数据库引用
  getDB() {
    return this.db
  }

  // ==================== 书籍操作 ====================

  /**
   * 获取书籍列表
   * @param {Object} params - 查询参数
   * @param {number} params.categoryId - 分类ID (0表示全部)
   * @param {number} params.limit - 每页数量
   * @param {number} params.skip - 跳过的数量
   */
  async getBooks(params = {}) {
    const { categoryId = 0, limit = 20, skip = 0 } = params

    // 优先使用云函数
    if (this.useCloudFunction) {
      try {
        const res = await wx.cloud.callFunction({
          name: 'getBooks',
          data: { categoryId, limit, skip }
        })

        if (res.result && res.result.success) {
          return res.result
        }
      } catch (err) {
        console.error('云函数 getBooks 调用失败，尝试直接查询', err)
      }
    }

    // 直接查询数据库（降级方案）
    try {
      let query = this.db.collection('books')

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
        data: res.data
      }
    } catch (err) {
      console.error('获取书籍列表失败', err)
      return {
        success: false,
        error: err.message,
        data: []
      }
    }
  }

  /**
   * 获取热门书籍
   * @param {number} limit - 返回数量
   */
  async getHotBooks(limit = 3) {
    try {
      const res = await this.db.collection('books')
        .where({ isHot: true })
        .limit(limit)
        .get()

      return {
        success: true,
        data: res.data
      }
    } catch (err) {
      console.error('获取热门书籍失败', err)
      return {
        success: false,
        error: err.message,
        data: []
      }
    }
  }

  /**
   * 获取最新书籍
   * @param {number} limit - 返回数量
   */
  async getLatestBooks(limit = 6) {
    try {
      const res = await this.db.collection('books')
        .orderBy('createTime', 'desc')
        .limit(limit)
        .get()

      return {
        success: true,
        data: res.data
      }
    } catch (err) {
      console.error('获取最新书籍失败', err)
      return {
        success: false,
        error: err.message,
        data: []
      }
    }
  }

  /**
   * 获取书籍详情
   * @param {string} bookId - 书籍ID
   */
  async getBookDetail(bookId) {
    // 优先使用云函数
    if (this.useCloudFunction) {
      try {
        const res = await wx.cloud.callFunction({
          name: 'getBookDetail',
          data: { bookId }
        })

        if (res.result && res.result.success) {
          return res.result
        }
      } catch (err) {
        console.error('云函数 getBookDetail 调用失败，尝试直接查询', err)
      }
    }

    // 直接查询数据库
    try {
      const res = await this.db.collection('books')
        .doc(bookId)
        .get()

      return {
        success: true,
        data: res.data
      }
    } catch (err) {
      console.error('获取书籍详情失败', err)
      return {
        success: false,
        error: err.message,
        data: null
      }
    }
  }

  /**
   * 搜索书籍
   * @param {string} keyword - 搜索关键词
   */
  async searchBooks(keyword) {
    if (!keyword) {
      return { success: true, data: [] }
    }

    // 优先使用云函数
    if (this.useCloudFunction) {
      try {
        const res = await wx.cloud.callFunction({
          name: 'searchBooks',
          data: { keyword }
        })

        if (res.result && res.result.success) {
          return res.result
        }
      } catch (err) {
        console.error('云函数 searchBooks 调用失败，尝试直接查询', err)
      }
    }

    // 直接查询数据库
    try {
      const res = await this.db.collection('books')
        .where({
          title: this.db.RegExp({
            regexp: keyword,
            options: 'i'
          })
        })
        .get()

      return {
        success: true,
        data: res.data
      }
    } catch (err) {
      console.error('搜索书籍失败', err)
      return {
        success: false,
        error: err.message,
        data: []
      }
    }
  }

  // ==================== 金句操作 ====================

  /**
   * 获取金句列表
   * @param {Object} params - 查询参数
   * @param {string} params.filter - 筛选类型 (all/hot/liked)
   * @param {string} params.bookId - 书籍ID (可选，用于获取某本书的金句)
   * @param {number} params.limit - 每页数量
   * @param {number} params.skip - 跳过的数量
   */
  async getQuotes(params = {}) {
    const { filter = 'all', bookId = null, limit = 20, skip = 0 } = params

    // 优先使用云函数
    if (this.useCloudFunction) {
      try {
        const res = await wx.cloud.callFunction({
          name: 'getQuotes',
          data: { filter, bookId, limit, skip }
        })

        if (res.result && res.result.success) {
          return res.result
        }
      } catch (err) {
        console.error('云函数 getQuotes 调用失败，尝试直接查询', err)
      }
    }

    // 直接查询数据库
    try {
      let query = this.db.collection('quotes')

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
          .where({ playCount: this.db.command.gte(1000) })
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
        data: res.data
      }
    } catch (err) {
      console.error('获取金句列表失败', err)
      return {
        success: false,
        error: err.message,
        data: []
      }
    }
  }

  /**
   * 获取每日金句
   */
  async getDailyQuote() {
    try {
      // 获取所有金句
      const res = await this.db.collection('quotes')
        .limit(100)
        .get()

      if (res.data.length === 0) {
        return {
          success: false,
          error: '暂无金句',
          data: null
        }
      }

      // 随机选择一条
      const index = Math.floor(Math.random() * res.data.length)
      return {
        success: true,
        data: res.data[index]
      }
    } catch (err) {
      console.error('获取每日金句失败', err)
      return {
        success: false,
        error: err.message,
        data: null
      }
    }
  }

  /**
   * 搜索金句
   * @param {string} keyword - 搜索关键词
   */
  async searchQuotes(keyword) {
    if (!keyword) {
      return { success: true, data: [] }
    }

    // 优先使用云函数
    if (this.useCloudFunction) {
      try {
        const res = await wx.cloud.callFunction({
          name: 'searchQuotes',
          data: { keyword }
        })

        if (res.result && res.result.success) {
          return res.result
        }
      } catch (err) {
        console.error('云函数 searchQuotes 调用失败，尝试直接查询', err)
      }
    }

    // 直接查询数据库
    try {
      const res = await this.db.collection('quotes')
        .where({
          content: this.db.RegExp({
            regexp: keyword,
            options: 'i'
          })
        })
        .get()

      return {
        success: true,
        data: res.data
      }
    } catch (err) {
      console.error('搜索金句失败', err)
      return {
        success: false,
        error: err.message,
        data: []
      }
    }
  }

  // ==================== 用户操作 ====================

  /**
   * 获取用户收藏的书籍
   * @param {Array} bookIds - 书籍ID数组
   */
  async getFavoriteBooks(bookIds) {
    if (!bookIds || bookIds.length === 0) {
      return { success: true, data: [] }
    }

    try {
      const res = await this.db.collection('books')
        .where({
          _id: this.db.command.in(bookIds)
        })
        .get()

      return {
        success: true,
        data: res.data
      }
    } catch (err) {
      console.error('获取收藏书籍失败', err)
      return {
        success: false,
        error: err.message,
        data: []
      }
    }
  }

  /**
   * 获取用户收藏的金句
   * @param {Array} quoteIds - 金句ID数组
   */
  async getFavoriteQuotes(quoteIds) {
    if (!quoteIds || quoteIds.length === 0) {
      return { success: true, data: [] }
    }

    try {
      const res = await this.db.collection('quotes')
        .where({
          _id: this.db.command.in(quoteIds)
        })
        .get()

      return {
        success: true,
        data: res.data
      }
    } catch (err) {
      console.error('获取收藏金句失败', err)
      return {
        success: false,
        error: err.message,
        data: []
      }
    }
  }

  // ==================== 通用云函数调用 ====================

  /**
   * 调用云函数
   * @param {string} name - 云函数名称
   * @param {Object} data - 传递给云函数的参数
   */
  async callFunction(name, data = {}) {
    try {
      const res = await wx.cloud.callFunction({
        name,
        data
      })

      return {
        success: true,
        data: res.result
      }
    } catch (err) {
      console.error(`调用云函数 ${name} 失败`, err)
      return {
        success: false,
        error: err.message,
        data: null
      }
    }
  }
}

// 导出单例
module.exports = new CloudDB()
