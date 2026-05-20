// app.js
const PlayerStore = require('./store/player.js')

App({
  globalData: {
    userInfo: null,
    // 播放器状态（兼容旧代码）
    player: {
      isPlaying: false,
      currentBook: null,
      currentQuote: null,
      currentTime: 0,
      progress: 0,
      duration: 0,
      _store: null
    },
    // API 基础地址
    apiBase: 'https://api.tingshujs.com',
    // 云开发环境ID
    cloudEnv: 'cloud1-d2ggs9k1bf3aa2a18'
  },
  
  onLaunch() {
    // 初始化云开发
    if (wx.cloud) {
      wx.cloud.init({
        env: this.globalData.cloudEnv || wx.cloud.DYNAMIC_CURRENT_ENV,
        traceUser: true
      })
    }
    
    // 检查登录状态
    this.checkLoginStatus()
    
    // 初始化播放器
    this.initPlayer()
  },
  
  checkLoginStatus() {
    const userInfo = wx.getStorageSync('userInfo')
    if (userInfo) {
      this.globalData.userInfo = userInfo
    }
  },
  
  initPlayer() {
    // 使用 BackgroundAudioManager（后台音频管理器），支持黑屏后继续播放
    const backgroundAudioManager = wx.getBackgroundAudioManager()
    
    // 初始化 PlayerStore
    const playerStore = new PlayerStore()
    playerStore.init(backgroundAudioManager)
    
    // 将 store 存入 globalData
    this.globalData.player._store = playerStore
    
    // 监听播放器事件，更新 globalData
    playerStore.addListener((data) => {
      this.globalData.player.isPlaying = data.isPlaying
      this.globalData.player.currentBook = data.currentBook
      this.globalData.player.progress = data.progress
      this.globalData.player.duration = data.duration
      // 同步播放进度（供其他页面使用）
      if (data.progress !== undefined) {
        this.globalData.player.currentTime = data.progress
      }
      // 更新历史记录进度（每5秒更新一次，避免频繁写入）
      if (data.progress !== undefined && data.duration > 0) {
        const now = Date.now()
        if (!this._lastHistoryUpdate || now - this._lastHistoryUpdate > 5000) {
          this._lastHistoryUpdate = now
          const percent = Math.round((data.progress / data.duration) * 100)
          this.updateHistoryProgress(data.progress, data.duration, percent)
        }
      }
    })
  },
  
  // 播放书籍
  playBook(book) {
    const store = this.globalData.player._store
    if (store) {
      store.play(book)
      // 同步到 globalData
      this.globalData.player.currentBook = book
      this.globalData.player.isPlaying = true
    } else {
      // 兼容模式：直接更新 globalData
      this.globalData.player.currentBook = book
      this.globalData.player.isPlaying = true
      this.globalData.player.currentTime = 0
      this.globalData.player.progress = 0
    }
    
    // 添加到播放历史
    this.addToHistory(book)
  },
  
  // 暂停播放
  pausePlay() {
    const store = this.globalData.player._store
    if (store) {
      store.pause()
    }
    this.globalData.player.isPlaying = false
  },
  
  // 切换播放状态
  togglePlay() {
    const store = this.globalData.player._store
    if (store) {
      store.toggle()
    } else {
      this.globalData.player.isPlaying = !this.globalData.player.isPlaying
    }
  },
  
  // 添加到历史记录
  addToHistory(book) {
    let history = wx.getStorageSync('playHistory') || []
    
    // 移除重复项
    history = history.filter(h => h.id !== book.id)
    
    // 添加到开头
    history.unshift({
      ...book,
      lastPlayTime: Date.now(),
      progress: 0
    })
    
    // 最多保留20条
    if (history.length > 20) {
      history = history.slice(0, 20)
    }
    
    wx.setStorageSync('playHistory', history)
  },
  
  // 更新播放进度（供页面调用）
  updateProgress(progress, currentTime) {
    this.globalData.player.progress = progress
    this.globalData.player.currentTime = currentTime
  },

  // 更新历史记录进度（内部使用）
  updateHistoryProgress(currentTime, duration, percent) {
    const history = wx.getStorageSync('playHistory') || []
    const book = this.globalData.player.currentBook
    if (book) {
      const index = history.findIndex(h => h.id === book.id)
      if (index !== -1) {
        history[index].currentTime = currentTime
        history[index].duration = duration
        history[index].progressPercent = percent
        history[index].lastPlayTime = Date.now()
        wx.setStorageSync('playHistory', history)
      }
    }
  },
  
  // 登录方法（模拟）
  login(callback) {
    // 模拟登录
    const mockUserInfo = {
      id: 'user_' + Date.now(),
      nickname: '书友' + Math.floor(Math.random() * 1000),
      avatar: ''
    }
    
    wx.setStorageSync('userInfo', mockUserInfo)
    this.globalData.userInfo = mockUserInfo
    
    if (callback) callback(mockUserInfo)
  },
  
  // 退出登录
  logout() {
    wx.removeStorageSync('userInfo')
    this.globalData.userInfo = null
  }
})
