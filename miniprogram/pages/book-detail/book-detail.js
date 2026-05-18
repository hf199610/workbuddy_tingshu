// pages/book-detail/book-detail.js - 书籍详情逻辑（云开发版）
const cloudDB = require('../../utils/clouddb.js')
const { CATEGORIES } = require('../../config/constants.js')

// 默认数据（降级方案）
const defaultQuotes = [
  { _id: 'dq1', content: '知识就是力量。', author: '培根', bookName: '论人生', playCount: 1000, likeCount: 200 },
  { _id: 'dq2', content: '书山有路勤为径，学海无涯苦作舟。', author: '韩愈', bookName: '古今贤文', playCount: 800, likeCount: 150 },
  { _id: 'dq3', content: '读万卷书，行万里路。', author: '顾炎武', bookName: '日知录', playCount: 600, likeCount: 100 }
]

Page({
  data: {
    bookId: null,
    book: null,
    categoryName: '',
    quotes: [],
    isFavorite: false,
    loading: true,
    showFullIntro: false,
    showFullScript: false,  // 展开全文状态
    showFullPlayer: false,
    showMiniPlayer: false,
    playerState: {
      title: '',
      subtitle: '',
      coverColor: '#667eea',
      isPlaying: false
    }
  },

  onLoad(options) {
    const bookId = options.id
    this.setData({ bookId })
    this.loadBookDetail(bookId)
  },

  onShow() {
    // 刷新收藏状态和播放器状态
    this.loadFavoriteStatus()
    this.updatePlayerState()
  },

  async loadBookDetail(bookId) {
    this.setData({ loading: true })

    // 先加载书籍详情
    const bookRes = await cloudDB.getBookDetail(bookId)
    console.log('书籍详情:', bookRes)
    
    // 再用书名查询金句
    const bookTitle = bookRes.data?.title
    console.log('书名:', bookTitle)
    const quotesRes = bookTitle ? await cloudDB.getQuotes({ bookName: bookTitle, limit: 10 }) : { success: false, data: [] }
    console.log('金句查询结果:', quotesRes)

    if (bookRes.success && bookRes.data) {
      const book = {
        ...bookRes.data,
        id: bookRes.data._id || bookRes.data.id,
        // 兼容字段名
        intro: bookRes.data.intro || bookRes.data.description || '',
        quotes: bookRes.data.quotes || []
      }

      // 获取分类名称
      const categoryName = CATEGORIES[book.category] || '未分类'

      // 处理金句数据 - 优先使用books中的quotes字段，其次才是云数据库查询
      let quotes = book.quotes || []
      if (quotes.length === 0 && quotesRes.success && quotesRes.data.length > 0) {
        quotes = quotesRes.data.map(q => ({
          ...q,
          id: q._id || q.id
        }))
      }
      
      // 如果还是没有，使用默认金句（作为后备）
      if (quotes.length === 0) {
        quotes = defaultQuotes
      }

      // 加载收藏状态
      const favoriteIds = wx.getStorageSync('favoriteBooks') || []
      const isFavorite = favoriteIds.includes(bookId) || favoriteIds.includes(book._id)

      this.setData({
        book,
        categoryName,
        quotes,
        isFavorite,
        loading: false,
        showFullScript: false
      })
    } else {
      wx.showToast({ title: '书籍不存在', icon: 'none' })
      setTimeout(() => {
        wx.navigateBack()
      }, 1500)
      this.setData({ loading: false })
    }
  },

  // 加载收藏状态
  loadFavoriteStatus() {
    if (!this.data.bookId) return
    const favoriteIds = wx.getStorageSync('favoriteBooks') || []
    const isFavorite = favoriteIds.includes(this.data.bookId)
    this.setData({ isFavorite })
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

  // 返回
  onBack() {
    wx.navigateBack()
  },

  // 菜单
  onMenuTap() {
    wx.showActionSheet({
      itemList: ['分享给好友', '复制链接', '举报'],
      success: (res) => {
        if (res.tapIndex === 0) {
          this.onShare()
        } else if (res.tapIndex === 1) {
          wx.setClipboardData({
            data: `听书金句 - ${this.data.book?.title || '书籍'}`,
            success: () => {
              wx.showToast({ title: '已复制', icon: 'success' })
            }
          })
        } else if (res.tapIndex === 2) {
          wx.showToast({ title: '感谢反馈', icon: 'success' })
        }
      }
    })
  },

  // 收藏
  onFavoriteTap() {
    const bookId = this.data.bookId || this.data.book?._id
    let favoriteIds = wx.getStorageSync('favoriteBooks') || []

    let isFavorite = this.data.isFavorite
    if (isFavorite) {
      // 取消收藏
      favoriteIds = favoriteIds.filter(id => id !== bookId)
      isFavorite = false
    } else {
      // 添加收藏
      favoriteIds.push(bookId)
      isFavorite = true
    }

    wx.setStorageSync('favoriteBooks', favoriteIds)
    this.setData({ isFavorite })

    wx.showToast({
      title: isFavorite ? '已收藏' : '已取消收藏',
      icon: 'success'
    })
  },

  // 播放
  onPlayTap() {
    const book = this.data.book
    if (!book) return

    // 检查是否有音频
    if (!book.audioUrl || book.audioUrl.length === 0) {
      wx.showToast({
        title: '音频生成中，敬请期待',
        icon: 'none'
      })
      return
    }

    // 显示播放提示
    wx.showToast({
      title: '正在缓冲…',
      icon: 'loading',
      duration: 1500
    })

    // 调用全局播放方法
    getApp().playBook(book)
    this.updatePlayerState()

    // 打开全屏播放器
    this.setData({ showFullPlayer: true })
  },

  // 展开/收起简介
  onToggleIntro() {
    this.setData({
      showFullIntro: !this.data.showFullIntro
    })
  },

  // 展开/收起简介
  onToggleIntro() {
    this.setData({
      showFullIntro: !this.data.showFullIntro
    })
  },

  // 展开/收起脚本
  onToggleScript() {
    this.setData({
      showFullScript: !this.data.showFullScript
    })
  },

  // 朗读简介
  onReadAloud() {
    wx.showToast({ title: '朗读功能开发中', icon: 'none' })
  },

  // 金句点赞
  onQuoteLike(e) {
    const quoteId = e.currentTarget.dataset.id
    const quotes = this.data.quotes.map(q => {
      if (q.id === quoteId) {
        return { ...q, likeCount: (q.likeCount || 0) + 1 }
      }
      return q
    })
    this.setData({ quotes })
    wx.showToast({ title: '已点赞', icon: 'success' })
  },

  // 复制金句
  onQuoteCopy(e) {
    const content = e.currentTarget.dataset.content
    wx.setClipboardData({
      data: `"${content}"`,
      success: () => {
        wx.showToast({ title: '已复制', icon: 'success' })
      }
    })
  },

  // 分享金句
  onQuoteShare(e) {
    this.onShare()
  },

  // 分享
  onShare() {
    const book = this.data.book
    if (!book) return

    wx.showModal({
      title: '分享',
      content: `《${book.title}》- ${book.author}\n\n推荐一个很棒的听书应用：「听书金句」`,
      confirmText: '复制',
      success: (res) => {
        if (res.confirm) {
          wx.setClipboardData({
            data: `《${book.title}》- ${book.author}\n\n推荐一个很棒的听书应用：「听书金句」`,
            success: () => {
              wx.showToast({ title: '已复制', icon: 'success' })
            }
          })
        }
      }
    })
  },

  // 打开全屏播放器
  onOpenPlayer() {
    this.setData({ showFullPlayer: true })
  },

  // 关闭全屏播放器
  onCloseFullPlayer() {
    this.setData({ showFullPlayer: false })
  },

  // 从全屏播放器返回
  onBackFromPlayer() {
    this.setData({ showFullPlayer: false })
  },

  // 播放器状态变化
  onPlayerStateChange() {
    this.updatePlayerState()
  },

  // 查看更多金句（预留）
  onShowMoreQuotes() {
    wx.showToast({ title: '金句列表已展示全部', icon: 'none' })
  }
})
