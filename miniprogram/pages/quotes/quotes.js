// pages/quotes/quotes.js - 金句列表逻辑（云开发版）
const cloudDB = require('../../utils/clouddb.js')

Page({
  data: {
    quotes: [],
    loading: true,
    showSearch: false,
    showMiniPlayer: false,
    playerState: {
      title: '',
      subtitle: '',
      coverColor: '#667eea',
      isPlaying: false
    }
  },

  onLoad() {
    this.loadQuotes()
  },

  onShow() {
    this.updatePlayerState()
  },

  onReachBottom() {
    // 加载更多
    if (!this.data.loading) {
      this.loadMore()
    }
  },

  // 更新播放器状态
  updatePlayerState() {
    const player = getApp().globalData.player
    const showMiniPlayer = !!player.currentBook

    this.setData({
      showMiniPlayer,
      playerState: {
        title: player.currentBook?.title || '',
        subtitle: player.currentBook?.author || '',
        coverColor: player.currentBook?.color || '#667eea',
        isPlaying: player.isPlaying
      }
    })
  },

  // 搜索
  onSearchTap() {
    this.setData({ showSearch: true })
  },

  onCloseSearch() {
    this.setData({ showSearch: false })
  },

  // 加载金句
  async loadQuotes() {
    this.setData({ loading: true })

    const res = await cloudDB.getQuotes({
      limit: 20,
      skip: 0
    })

    // 加载收藏状态
    const favoriteIds = wx.getStorageSync('favoriteQuotes') || []

    let quotes = []
    if (res.success && res.data.length > 0) {
      quotes = res.data.map(q => ({
        ...q,
        id: q._id || q.id,
        isFavorite: favoriteIds.includes(q._id) || favoriteIds.includes(q.id)
      }))
    }

    // 如果没有数据，显示提示
    if (quotes.length === 0) {
      wx.showToast({
        title: '暂无金句数据，请先在云开发控制台添加',
        icon: 'none',
        duration: 2000
      })
    }

    this.setData({
      quotes,
      loading: false
    })
  },

  // 加载更多
  async loadMore() {
    const res = await cloudDB.getQuotes({
      limit: 20,
      skip: this.data.quotes.length
    })

    if (res.success && res.data.length > 0) {
      const favoriteIds = wx.getStorageSync('favoriteQuotes') || []

      const newQuotes = res.data.map(q => ({
        ...q,
        id: q._id || q.id,
        isFavorite: favoriteIds.includes(q._id) || favoriteIds.includes(q.id)
      }))

      this.setData({
        quotes: [...this.data.quotes, ...newQuotes]
      })

      wx.showToast({
        title: '加载了 ' + newQuotes.length + ' 条金句',
        icon: 'none'
      })
    } else {
      wx.showToast({
        title: '没有更多了',
        icon: 'none'
      })
    }
  },

  // 下拉刷新
  onPullDownRefresh() {
    this.loadQuotes().then(() => {
      wx.stopPullDownRefresh()
    })
  },

  // 金句点击 - 跳转到书籍详情
  onQuoteTap(e) {
    const bookId = e.currentTarget.dataset.bookid
    if (bookId) {
      wx.navigateTo({
        url: '/pages/book-detail/book-detail?id=' + bookId
      })
    } else {
      wx.showToast({ title: '暂无该书详情', icon: 'none' })
    }
  },

  // 播放金句
  async onPlayQuote(e) {
    const quoteId = e.currentTarget.dataset.id
    const quote = this.data.quotes.find(q => q.id === quoteId)

    if (!quote) return

    // 如果有对应的书籍，播放书籍
    if (quote.bookId) {
      const res = await cloudDB.getBookDetail(quote.bookId)
      if (res.success && res.data) {
        const book = {
          ...res.data,
          id: res.data._id || res.data.id
        }
        getApp().playBook(book)
        this.updatePlayerState()
        wx.showToast({ title: '开始播放: ' + book.title, icon: 'none' })
        return
      }
    }

    wx.showToast({ title: '播放功能开发中', icon: 'none' })
  },

  // 复制金句
  onCopyQuote(e) {
    const content = e.currentTarget.dataset.content
    wx.setClipboardData({
      data: `"${content}"`,
      success: () => {
        wx.showToast({ title: '已复制', icon: 'success' })
      }
    })
  },

  // 收藏金句
  onFavoriteQuote(e) {
    const quoteId = e.currentTarget.dataset.id
    let favoriteIds = wx.getStorageSync('favoriteQuotes') || []

    const quoteIndex = this.data.quotes.findIndex(q => q.id === quoteId)
    const isFavorite = this.data.quotes[quoteIndex].isFavorite

    if (isFavorite) {
      // 取消收藏
      favoriteIds = favoriteIds.filter(id => id !== quoteId)
    } else {
      // 添加收藏
      favoriteIds.push(quoteId)
    }

    wx.setStorageSync('favoriteQuotes', favoriteIds)

    // 更新本地数据
    const quotes = [...this.data.quotes]
    quotes[quoteIndex].isFavorite = !isFavorite
    this.setData({ quotes })

    wx.showToast({
      title: isFavorite ? '已取消收藏' : '已收藏',
      icon: 'success'
    })
  },

  // 打开全屏播放器
  onOpenPlayer() {
    const app = getApp()
    if (app.globalData.player.currentBook) {
      wx.navigateTo({
        url: '/pages/book-detail/book-detail?id=' + (app.globalData.player.currentBook._id || app.globalData.player.currentBook.id)
      })
    }
  }
})
