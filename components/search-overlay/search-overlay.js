// components/search-overlay/search-overlay.js - 搜索覆盖层逻辑（云开发版）
const cloudDB = require('../../utils/clouddb.js')

// 分类映射
const categoryMap = {
  1: '经典名著',
  2: '科幻小说',
  3: '历史文学',
  4: '哲学思考',
  5: '商业经济',
  6: '心理励志',
  7: '散文随笔'
}

Component({
  properties: {
    show: {
      type: Boolean,
      value: false
    }
  },

  data: {
    keyword: '',
    searchType: 'all',
    searchHistory: [],
    hotKeywords: ['红楼梦', '三体', '小王子', '活着', '人类简史', '百年孤独'],
    bookResults: [],
    quoteResults: [],
    searching: false
  },

  lifetimes: {
    attached() {
      const history = wx.getStorageSync('searchHistory') || []
      this.setData({ searchHistory: history })
    }
  },

  methods: {
    // 输入
    onInput(e) {
      const keyword = e.detail.value
      this.setData({ keyword })

      if (keyword.length > 0) {
        // 防抖处理
        if (this.searchTimer) {
          clearTimeout(this.searchTimer)
        }
        this.searchTimer = setTimeout(() => {
          this.doSearch(keyword)
        }, 300)
      } else {
        this.setData({
          bookResults: [],
          quoteResults: []
        })
      }
    },

    // 搜索
    onSearch() {
      const { keyword } = this.data
      if (!keyword) return

      this.saveHistory(keyword)
      this.doSearch(keyword)
    },

    // 执行搜索（云开发版）
    async doSearch(keyword) {
      if (!keyword) return

      const { searchType } = this.data
      this.setData({ searching: true })

      try {
        // 并行搜索书籍和金句
        let bookPromise = Promise.resolve({ success: true, data: [] })
        let quotePromise = Promise.resolve({ success: true, data: [] })

        if (searchType === 'all' || searchType === 'book') {
          bookPromise = cloudDB.searchBooks(keyword)
        }

        if (searchType === 'all' || searchType === 'quote') {
          quotePromise = cloudDB.searchQuotes(keyword)
        }

        const [bookRes, quoteRes] = await Promise.all([bookPromise, quotePromise])

        // 处理书籍结果
        let bookResults = []
        if (bookRes.success && bookRes.data) {
          bookResults = bookRes.data.map(b => ({
            ...b,
            id: b._id || b.id,
            categoryName: categoryMap[b.category] || '未分类'
          }))
        }

        // 处理金句结果
        let quoteResults = []
        if (quoteRes.success && quoteRes.data) {
          quoteResults = quoteRes.data.map(q => ({
            ...q,
            id: q._id || q.id
          }))
        }

        this.setData({
          bookResults,
          quoteResults,
          searching: false
        })
      } catch (err) {
        console.error('搜索失败', err)
        this.setData({
          bookResults: [],
          quoteResults: [],
          searching: false
        })
        wx.showToast({
          title: '搜索失败，请重试',
          icon: 'none'
        })
      }
    },

    // 保存历史
    saveHistory(keyword) {
      let history = wx.getStorageSync('searchHistory') || []
      history = history.filter(h => h !== keyword)
      history.unshift(keyword)
      if (history.length > 10) history = history.slice(0, 10)

      wx.setStorageSync('searchHistory', history)
      this.setData({ searchHistory: history })
    },

    // 清空历史
    onClearHistory() {
      wx.removeStorageSync('searchHistory')
      this.setData({ searchHistory: [] })
    },

    // 历史点击
    onHistoryTap(e) {
      const keyword = e.currentTarget.dataset.keyword
      this.setData({ keyword })
      this.doSearch(keyword)
    },

    // 类型切换
    onTypeChange(e) {
      const searchType = e.currentTarget.dataset.type
      this.setData({ searchType })

      if (this.data.keyword) {
        this.doSearch(this.data.keyword)
      }
    },

    // 清空输入
    onClear() {
      if (this.searchTimer) {
        clearTimeout(this.searchTimer)
      }
      this.setData({
        keyword: '',
        bookResults: [],
        quoteResults: []
      })
    },

    // 取消
    onCancel() {
      this.triggerEvent('close')
    },

    // 书籍点击
    onBookTap(e) {
      const bookId = e.currentTarget.dataset.id
      this.triggerEvent('close')
      wx.navigateTo({
        url: '/pages/book-detail/book-detail?id=' + bookId
      })
    }
  }
})
