// pages/user/user.js - 个人中心逻辑（云开发版）
const app = getApp()
const cloudDB = require('../../utils/clouddb.js')

Page({
  data: {
    favBookCount: 0,
    favQuoteCount: 0,
    listenCount: 0,
    currentFavTab: 'books',
    favBooks: [],
    favQuotes: [],
    histories: [],
    loading: true,
    showMiniPlayer: false,
    playerState: {
      title: '',
      subtitle: '',
      coverColor: '#667eea',
      isPlaying: false
    }
  },

  onLoad() {
    this.loadData()
  },

  onShow() {
    this.loadData()
    this.updatePlayerState()
  },

  async loadData() {
    this.setData({ loading: true })

    // 从本地存储获取收藏ID
    const favoriteBookIds = wx.getStorageSync('favoriteBooks') || []
    const favoriteQuoteIds = wx.getStorageSync('favoriteQuotes') || []
    let histories = wx.getStorageSync('playHistory') || []

    // 处理历史记录：计算播放百分比
    histories = histories.map(h => {
      let percent = h.progressPercent || 0
      // 兼容旧数据：如果存储的是秒数，计算百分比
      if (!percent && h.currentTime && h.duration) {
        percent = Math.round((h.currentTime / h.duration) * 100)
      } else if (!percent && typeof h.progress === 'number' && h.progress > 0 && h.progress <= 1) {
        // progress 可能是小数比例（0-1）
        percent = Math.round(h.progress * 100)
      } else if (!percent && typeof h.progress === 'number' && h.progress > 1) {
        // progress 可能是秒数，尝试计算
        const duration = h.audioDuration || h.duration || 0
        if (duration > 0) {
          percent = Math.round((h.progress / duration) * 100)
        }
      }
      return {
        ...h,
        progress: Math.min(percent, 100) // 确保不超过100%
      }
    })

    // 并行加载收藏的书籍和金句
    const [bookRes, quoteRes] = await Promise.all([
      cloudDB.getFavoriteBooks(favoriteBookIds),
      cloudDB.getFavoriteQuotes(favoriteQuoteIds)
    ])

    // 处理书籍数据
    const favBooks = bookRes.success
      ? bookRes.data.map(b => ({ ...b, id: b._id || b.id }))
      : []

    // 处理金句数据
    const favQuotes = quoteRes.success
      ? quoteRes.data.map(q => ({ ...q, id: q._id || q.id }))
      : []

    this.setData({
      favBookCount: favBooks.length || favoriteBookIds.length,
      favQuoteCount: favQuotes.length || favoriteQuoteIds.length,
      listenCount: histories.length,
      favBooks,
      favQuotes,
      histories,
      loading: false
    })
  },

  // 更新播放器状态
  updatePlayerState() {
    const player = app.globalData.player
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

  // 收藏Tab切换
  onFavTabTap(e) {
    const type = e.currentTarget.dataset.type
    this.setData({ currentFavTab: type })
  },

  // 书籍点击
  onBookTap(e) {
    const bookId = e.currentTarget.dataset.id
    if (bookId) {
      wx.navigateTo({
        url: '/pages/book-detail/book-detail?id=' + bookId
      })
    }
  },

  // 历史点击
  onHistoryTap(e) {
    const bookId = e.currentTarget.dataset.id
    if (bookId) {
      wx.navigateTo({
        url: '/pages/book-detail/book-detail?id=' + bookId
      })
    }
  },

  // 播放金句
  async onPlayQuote(e) {
    const quoteId = e.currentTarget.dataset.id
    const quote = this.data.favQuotes.find(q => q.id === quoteId)

    if (!quote) return

    if (quote.bookId) {
      const res = await cloudDB.getBookDetail(quote.bookId)
      if (res.success && res.data) {
        const book = {
          ...res.data,
          id: res.data._id || res.data.id
        }
        app.playBook(book)
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

  // 去探索
  onGoExplore() {
    wx.switchTab({ url: '/pages/books/books' })
  },

  // 菜单点击
  onMenuTap(e) {
    const type = e.currentTarget.dataset.type

    switch (type) {
      case 'about':
        wx.showModal({
          title: '关于我们',
          content: '听书金句 v1.0.0\n\n为您提供经典书籍的精华讲解和名人金句，让阅读变得更简单。',
          showCancel: false,
          confirmText: '知道了'
        })
        break
      case 'privacy':
        wx.showModal({
          title: '隐私政策',
          content: '听书金句非常重视用户隐私保护。我们承诺：\n\n1. 不会收集您的个人信息\n2. 不会向第三方共享您的数据\n3. 本地数据仅存储在您的设备上',
          showCancel: false,
          confirmText: '知道了'
        })
        break
      case 'feedback':
        wx.showModal({
          title: '意见反馈',
          content: '如果您有好的建议或发现了问题，欢迎反馈。',
          editable: true,
          placeholderText: '请输入您的反馈...',
          success: (res) => {
            if (res.confirm && res.content) {
              wx.showToast({ title: '感谢反馈', icon: 'success' })
            }
          }
        })
        break
    }
  },

  // 打开全屏播放器
  onOpenPlayer() {
    if (app.globalData.player.currentBook) {
      wx.navigateTo({
        url: '/pages/book-detail/book-detail?id=' + (app.globalData.player.currentBook._id || app.globalData.player.currentBook.id)
      })
    }
  }
})
