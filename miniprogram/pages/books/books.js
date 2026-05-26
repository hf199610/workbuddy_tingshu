// pages/books/books.js - 书籍列表逻辑（云开发版）
const cloudDB = require('../../utils/clouddb.js')
const { CATEGORY_LIST } = require('../../config/constants.js')

Page({
  data: {
    categories: CATEGORY_LIST,
    categoryId: 0,
    books: [],
    totalCount: 0,
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
    this.loadBooks(0)
  },

  onShow() {
    this.updatePlayerState()
  },

  onReachBottom() {
    // 加载更多（分页）
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

  // 分类切换
  onCategoryTap(e) {
    const categoryId = e.currentTarget.dataset.id
    this.setData({ categoryId })
    this.loadBooks(categoryId)
  },

  // 加载书籍
  async loadBooks(categoryId) {
    this.setData({ loading: true })

    const res = await cloudDB.getBooks({
      categoryId,
      limit: 20,
      skip: 0
    })

    let books = []
    if (res.success && res.data.length > 0) {
      books = res.data.map(book => ({
        ...book,
        id: book._id || book.id
      }))
    }

    // 如果没有数据，显示空状态提示
    if (books.length === 0) {
      wx.showToast({
        title: '暂无书籍数据，请先在云开发控制台添加',
        icon: 'none',
        duration: 2000
      })
    }

    this.setData({
      books,
      totalCount: books.length,
      loading: false
    })
  },

  // 加载更多
  async loadMore() {
    const res = await cloudDB.getBooks({
      categoryId: this.data.categoryId,
      limit: 20,
      skip: this.data.books.length
    })

    if (res.success && res.data.length > 0) {
      const newBooks = res.data.map(book => ({
        ...book,
        id: book._id || book.id
      }))

      this.setData({
        books: [...this.data.books, ...newBooks],
        totalCount: this.data.books.length + newBooks.length
      })

      wx.showToast({
        title: '加载了 ' + newBooks.length + ' 本书',
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
    this.loadBooks(this.data.categoryId).then(() => {
      wx.stopPullDownRefresh()
    })
  },

  // 书籍点击
  onBookTap(e) {
    const bookId = e.currentTarget.dataset.id
    wx.navigateTo({
      url: '/pages/book-detail/book-detail?id=' + bookId
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
