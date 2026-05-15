// pages/index/index.js - 首页逻辑（云开发版）
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

// 默认数据（云开发未配置时的降级方案）
const defaultHotBooks = [
  { _id: '1', title: '红楼梦', author: '曹雪芹', category: 1, coverColor: '#e74c3c', description: '中国古典小说巅峰之作', isHot: true },
  { _id: '2', title: '三体', author: '刘慈欣', category: 2, coverColor: '#3498db', description: '亚洲首部雨果奖获奖科幻小说', isHot: true },
  { _id: '3', title: '人类简史', author: '尤瓦尔·赫拉利', category: 3, coverColor: '#9b59b6', description: '从动物到上帝的演化之路', isHot: true }
]

const defaultQuotes = [
  { _id: 'q1', content: '满纸荒唐言，一把辛酸泪。', author: '曹雪芹', bookName: '红楼梦', bookId: '1', playCount: 5200, likeCount: 1200 },
  { _id: 'q2', content: '给岁月以文明，而不是给文明以岁月。', author: '刘慈欣', bookName: '三体', bookId: '2', playCount: 3800, likeCount: 980 },
  { _id: 'q3', content: '历史从不等待任何一个人。', author: '尤瓦尔·赫拉利', bookName: '人类简史', bookId: '3', playCount: 2100, likeCount: 560 }
]

Page({
  data: {
    hotBooks: [],
    latestBooks: [],
    categories: ['全部', '经典名著', '科幻小说', '历史文学', '哲学思考'],
    currentCategory: 0,
    todayQuote: {},
    showSearch: false,
    showFullPlayer: false,
    showMiniPlayer: false,
    loading: true,
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
    this.updatePlayerState()
  },

  async loadData() {
    this.setData({ loading: true })

    // 并行加载热门书籍和最新书籍
    const [hotRes, latestRes, quoteRes] = await Promise.all([
      cloudDB.getHotBooks(3),
      cloudDB.getLatestBooks(6),
      cloudDB.getDailyQuote()
    ])

    // 处理热门书籍
    let hotBooks = hotRes.success ? hotRes.data : defaultHotBooks
    hotBooks = hotBooks.slice(0, 3).map(book => ({
      ...book,
      categoryName: categoryMap[book.category] || '其他',
      id: book._id || book.id
    }))

    // 处理最新书籍
    let latestBooks = latestRes.success ? latestRes.data : []
    latestBooks = latestBooks.slice(0, 6).map(book => ({
      ...book,
      categoryName: categoryMap[book.category] || '其他',
      id: book._id || book.id
    }))

    // 处理每日金句
    const todayQuote = quoteRes.success && quoteRes.data
      ? quoteRes.data
      : defaultQuotes[Math.floor(Math.random() * defaultQuotes.length)]

    this.setData({
      hotBooks,
      latestBooks,
      todayQuote,
      loading: false
    })
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

  // 书籍点击
  onBookTap(e) {
    const bookId = e.currentTarget.dataset.id
    wx.navigateTo({
      url: '/pages/book-detail/book-detail?id=' + bookId
    })
  },

  // 更多书籍
  onMoreBooks() {
    wx.switchTab({ url: '/pages/books/books' })
  },

  // 快速入口
  onEntryTap(e) {
    const type = e.currentTarget.dataset.type
    switch (type) {
      case 'books':
        wx.switchTab({ url: '/pages/books/books' })
        break
      case 'quotes':
        wx.switchTab({ url: '/pages/quotes/quotes' })
        break
      case 'favorites':
        wx.switchTab({ url: '/pages/user/user' })
        break
      case 'history':
        wx.switchTab({ url: '/pages/user/user' })
        break
    }
  },

  // 分类点击
  onCategoryTap(e) {
    const index = e.currentTarget.dataset.index
    this.setData({ currentCategory: index })
    wx.showToast({
      title: '已选择: ' + this.data.categories[index],
      icon: 'none'
    })
  },

  // 刷新金句
  onRefreshQuote() {
    this.refreshQuote()
    wx.showToast({
      title: '已刷新',
      icon: 'success',
      duration: 1000
    })
  },

  async refreshQuote() {
    const res = await cloudDB.getDailyQuote()
    const quote = res.success && res.data
      ? res.data
      : defaultQuotes[Math.floor(Math.random() * defaultQuotes.length)]
    this.setData({ todayQuote: quote })
  },

  // 复制金句
  onCopyQuote() {
    const quote = this.data.todayQuote
    if (!quote.content) return

    wx.setClipboardData({
      data: `"${quote.content}" —— ${quote.author}《${quote.bookName || '未知'}》`,
      success() {
        wx.showToast({ title: '已复制', icon: 'success' })
      }
    })
  },

  // 分享金句
  onShareQuote() {
    wx.showToast({ title: '分享功能开发中', icon: 'none' })
  },

  // 金句点击 - 播放
  onQuoteTap() {
    const quote = this.data.todayQuote
    if (quote.bookId) {
      // 根据 bookId 获取书籍信息并播放
      this.playBookById(quote.bookId)
    } else {
      wx.showToast({ title: '暂无该书详情', icon: 'none' })
    }
  },

  // 根据ID播放书籍
  async playBookById(bookId) {
    const res = await cloudDB.getBookDetail(bookId)
    if (res.success && res.data) {
      const book = {
        ...res.data,
        id: res.data._id || res.data.id
      }
      this.playBook(book)
    } else {
      wx.showToast({ title: '暂无该书详情', icon: 'none' })
    }
  },

  // 播放书籍
  playBook(book) {
    getApp().playBook(book)
    this.updatePlayerState()
    this.setData({ showFullPlayer: true })
  },

  // 打开全屏播放器
  onOpenPlayer() {
    this.setData({ showFullPlayer: true })
  },

  // 关闭全屏播放器
  onCloseFullPlayer() {
    this.setData({ showFullPlayer: false })
  },

  // 播放器状态变化
  onPlayerStateChange(e) {
    this.updatePlayerState()
  },

  // 上一曲
  onPrev() {
    wx.showToast({ title: '已是第一首', icon: 'none' })
  },

  // 下一曲
  onNext() {
    const player = getApp().globalData.player
    const currentBook = player.currentBook
    if (!currentBook) return

    const currentIndex = this.data.latestBooks.findIndex(b => b.id === currentBook.id)
    const nextBook = this.data.latestBooks[(currentIndex + 1) % this.data.latestBooks.length]

    if (nextBook) {
      this.playBook(nextBook)
    }
  }
})
