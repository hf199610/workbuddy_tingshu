// components/full-player/full-player.js - 全屏播放器逻辑
const app = getApp()

Component({
  properties: {
    show: {
      type: Boolean,
      value: false
    }
  },

  data: {
    title: '',
    author: '',
    duration: '00:00',
    coverColor: '#667eea',
    isPlaying: false,
    isFavorite: false,
    progress: 0,
    currentTime: '00:00',
    totalTime: '00:00',
    // 模拟音频时长（秒）
    _duration: 0,
    _currentTime: 0,
    _timer: null
  },

  lifetimes: {
    attached() {
      this.initFromApp()
    },
    detached() {
      this._clearTimer()
    }
  },

  pageLifetimes: {
    show() {
      this.initFromApp()
    }
  },

  methods: {
    // 从全局获取播放器状态
    initFromApp() {
      const player = app.globalData.player
      if (player.currentBook) {
        this.setData({
          title: player.currentBook.title,
          author: player.currentBook.author,
          coverColor: player.currentBook.color || '#667eea',
          duration: player.currentBook.duration || '00:00',
          isPlaying: player.isPlaying,
          isFavorite: player.currentBook.isFavorite || false,
          progress: player.progress || 0,
          currentTime: this._formatTime(player.currentTime || 0),
          totalTime: player.currentBook.duration || '00:00'
        })
      }
    },

    // 格式化时间
    _formatTime(seconds) {
      const mins = Math.floor(seconds / 60)
      const secs = Math.floor(seconds % 60)
      return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
    },

    // 解析时长字符串
    _parseDuration(str) {
      // 假设格式为 "MM:SS" 或 "HH:MM:SS"
      const parts = str.split(':').map(Number)
      if (parts.length === 2) {
        return parts[0] * 60 + parts[1]
      } else if (parts.length === 3) {
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
      }
      return 0
    },

    // 播放/暂停
    onPlayPause() {
      const isPlaying = !this.data.isPlaying
      this.setData({ isPlaying })
      app.globalData.player.isPlaying = isPlaying

      if (isPlaying) {
        this._startTimer()
      } else {
        this._clearTimer()
      }

      this.triggerEvent('statechange', { isPlaying })
    },

    // 开始计时器（模拟播放进度）
    _startTimer() {
      this._clearTimer()
      
      // 解析总时长
      if (!this._duration && this.data.duration) {
        this._duration = this._parseDuration(this.data.duration)
        this._currentTime = app.globalData.player.currentTime || 0
      }

      this._timer = setInterval(() => {
        if (this._currentTime < this._duration) {
          this._currentTime += 1
          const progress = (this._currentTime / this._duration) * 100
          
          this.setData({
            currentTime: this._formatTime(this._currentTime),
            progress: progress
          })
          
          app.globalData.player.currentTime = this._currentTime
          app.globalData.player.progress = progress
        } else {
          // 播放完成
          this._clearTimer()
          this.setData({ isPlaying: false })
          app.globalData.player.isPlaying = false
          this.triggerEvent('statechange', { isPlaying: false })
          this.triggerEvent('ended')
        }
      }, 1000)
    },

    _clearTimer() {
      if (this._timer) {
        clearInterval(this._timer)
        this._timer = null
      }
    },

    // 上一曲
    onPrev() {
      wx.showToast({ title: '上一曲', icon: 'none' })
      this.triggerEvent('prev')
    },

    // 下一曲
    onNext() {
      wx.showToast({ title: '下一曲', icon: 'none' })
      this.triggerEvent('next')
    },

    // 收藏
    onFavorite() {
      const isFavorite = !this.data.isFavorite
      this.setData({ isFavorite })
      
      if (app.globalData.player.currentBook) {
        app.globalData.player.currentBook.isFavorite = isFavorite
      }
      
      wx.showToast({
        title: isFavorite ? '已收藏' : '取消收藏',
        icon: 'success'
      })
      this.triggerEvent('favorite', { isFavorite })
    },

    // 分享
    onShare() {
      wx.showToast({ title: '分享功能开发中', icon: 'none' })
    },

    // 进度条点击
    onProgressTap(e) {
      const { duration } = this.data
      if (!duration || duration === '00:00') return

      const _duration = this._parseDuration(duration)
      const rect = e.currentTarget.boundingClientRect()
      const offsetX = e.detail.x || (e.touches && e.touches[0] ? e.touches[0].clientX - rect.left : 0)
      const ratio = offsetX / rect.width
      const newTime = Math.floor(ratio * _duration)

      this._currentTime = newTime
      const progress = (newTime / _duration) * 100

      this.setData({
        currentTime: this._formatTime(newTime),
        progress: progress
      })

      app.globalData.player.currentTime = newTime
      app.globalData.player.progress = progress
    },

    // 关闭
    onClose() {
      this._clearTimer()
      this.triggerEvent('close')
    },

    // 遮罩点击
    onMaskTap() {
      // 不关闭，点击内容区域才关闭
    },

    // 内容区域点击
    onContentTap() {
      // 阻止冒泡
    }
  }
})
