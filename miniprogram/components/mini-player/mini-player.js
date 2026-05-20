// components/mini-player/mini-player.js - 迷你播放器逻辑
const app = getApp()

Component({
  properties: {
    show: {
      type: Boolean,
      value: false
    },
    title: {
      type: String,
      value: ''
    },
    subtitle: {
      type: String,
      value: ''
    },
    coverColor: {
      type: String,
      value: '#667eea'
    },
    isPlaying: {
      type: Boolean,
      value: false
    }
  },

  data: {
    _isReady: false
  },

  lifetimes: {
    attached() {
      this._isReady = true
      // 初始同步
      this.syncFromGlobal()
      // 监听全局状态变化
      this._observer = app.globalData.player
    },
    detached() {
      this._isReady = false
    }
  },

  pageLifetimes: {
    show() {
      this.syncFromGlobal()
    }
  },

  methods: {
    // 从全局同步状态
    syncFromGlobal() {
      const player = app.globalData.player
      const book = player.currentBook
      
      if (book) {
        this.setData({
          show: true,
          title: book.title,
          subtitle: book.author || '',
          coverColor: book.color || '#667eea',
          isPlaying: player.isPlaying
        })
      } else {
        this.setData({
          show: false
        })
      }
    },

    // 打开全屏播放器
    onPlayerTap() {
      this.triggerEvent('openplayer')
    },

    // 播放/暂停
    onPlayTap() {
      const isPlaying = !this.data.isPlaying
      this.setData({ isPlaying })
      
      if (isPlaying) {
        app.globalData.player.isPlaying = true
        // 优先使用resume继续播放，失败则使用play
        const store = app.globalData.player._store
        if (store && store.audioContext && store.audioContext.src) {
          store.resume()
        } else {
          store?.play(app.globalData.player.currentBook)
        }
      } else {
        app.globalData.player.isPlaying = false
        app.globalData.player._store?.pause()
      }
      
      this.triggerEvent('play', { isPlaying })
    }
  }
})
