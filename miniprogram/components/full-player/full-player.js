// components/full-player/full-player.js - 全屏播放器（真实音频 + 字幕同步）
const app = getApp()

Component({
  properties: {
    show: {
      type: Boolean,
      value: false,
      observer: 'onShowChange'
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
    // 字幕相关
    subtitles: [],
    currentSubtitleIndex: -1,
    hasAudio: false,
    // 模拟播放（无真实音频时的降级方案）
    _duration: 0,
    _currentTime: 0,
    _timer: null,
    _useSimulated: false, // 是否使用模拟播放
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
    // 监听show属性变化 - 当显示全屏播放器时重新加载数据
    onShowChange(newVal) {
      if (newVal) {
        this.initFromApp()
      }
    },

    // 从全局获取播放器状态
    initFromApp() {
      const player = app.globalData.player
      const store = player._store
      if (player.currentBook) {
        const book = player.currentBook
        const subtitles = store.subtitles || []
        const hasAudio = !!(book.audioUrl && book.audioUrl.length > 0)

        this.setData({
          title: book.title,
          author: book.author,
          coverColor: book.color || '#667eea',
          duration: book.audioDurationText || book.duration || '00:00',
          isPlaying: player.isPlaying,
          isFavorite: book.isFavorite || false,
          progress: player.progress || 0,
          currentTime: this._formatTime(store.progress || 0),
          totalTime: book.audioDurationText || this._formatTime(store.duration || 0),
          subtitles: subtitles,
          currentSubtitleIndex: store.currentSubtitleIndex || -1,
          hasAudio: hasAudio,
          _useSimulated: !hasAudio,
        })

        // 如果有真实音频，设置音频事件监听
        if (hasAudio && store.audioContext) {
          this._setupAudioListeners(store.audioContext)
        }

        // 如果正在播放且使用模拟模式，启动模拟计时器
        if (player.isPlaying && !hasAudio) {
          this._startTimer()
        }
      }
    },

    // 设置真实音频事件监听
    _setupAudioListeners(audioCtx) {
      // 移除旧监听
      if (this._onTimeUpdate) {
        audioCtx.offTimeUpdate(this._onTimeUpdate)
      }
      if (this._onEnded) {
        audioCtx.offEnded(this._onEnded)
      }

      // 注册新监听
      this._onTimeUpdate = () => {
        const currentTime = audioCtx.currentTime || 0
        const duration = audioCtx.duration || 0
        const progress = duration > 0 ? (currentTime / duration) * 100 : 0

        // 获取字幕索引（从 store 读取，store 已在 onTimeUpdate 中计算）
        const store = app.globalData.player._store
        const subtitleIndex = store.currentSubtitleIndex || -1

        this.setData({
          currentTime: this._formatTime(currentTime),
          totalTime: this._formatTime(duration),
          progress: progress,
          currentSubtitleIndex: subtitleIndex,
          isPlaying: true,
        })
      }

      this._onEnded = () => {
        this.setData({
          isPlaying: false,
          currentSubtitleIndex: -1,
        })
        this._clearTimer()
        this.triggerEvent('statechange', { isPlaying: false })
        this.triggerEvent('ended')
      }

      audioCtx.onTimeUpdate(this._onTimeUpdate)
      audioCtx.onEnded(this._onEnded)
    },

    // 格式化时间
    _formatTime(seconds) {
      if (!seconds || isNaN(seconds)) return '00:00'
      seconds = Math.floor(seconds)
      const mins = Math.floor(seconds / 60)
      const secs = seconds % 60
      return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
    },

    // 解析时长字符串
    _parseDuration(str) {
      if (!str || str === '00:00') return 0
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
      const store = app.globalData.player._store
      const hasAudio = this.data.hasAudio

      // 计算点击后的播放状态
      let willPlay = !this.data.isPlaying

      if (hasAudio) {
        // 真实音频播放
        if (willPlay) {
          store.play(store.currentBook)
        } else {
          store.pause()
        }
      } else {
        // 模拟播放
        this.setData({ isPlaying: willPlay })
        app.globalData.player.isPlaying = willPlay

        if (willPlay) {
          this._startTimer()
        } else {
          this._clearTimer()
        }
      }

      // 发送正确的事件状态
      this.triggerEvent('statechange', { isPlaying: willPlay })
    },

    // 开始计时器（模拟播放进度 - 无真实音频时使用）
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
          const progress = this._duration > 0 ? (this._currentTime / this._duration) * 100 : 0

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
      const store = app.globalData.player._store
      const hasAudio = this.data.hasAudio

      if (hasAudio && store.audioContext) {
        // 真实 seek
        const duration = store.audioContext.duration || 0
        if (duration <= 0) return

        const query = wx.createSelectorQuery().in(this)
        query.select('.progress-bar').boundingClientRect()
        query.exec((res) => {
          if (!res || !res[0]) return
          const rect = res[0]
          const offsetX = e.detail.x - rect.left
          const ratio = Math.max(0, Math.min(1, offsetX / rect.width))
          const newTime = Math.floor(ratio * duration)

          store.seek(newTime)

          this.setData({
            currentTime: this._formatTime(newTime),
            progress: ratio * 100,
          })
        })
      } else {
        // 模拟 seek
        const _duration = this._parseDuration(this.data.duration)
        if (_duration <= 0) return

        const query = wx.createSelectorQuery().in(this)
        query.select('.progress-bar').boundingClientRect()
        query.exec((res) => {
          if (!res || !res[0]) return
          const rect = res[0]
          const offsetX = e.detail.x - rect.left
          const ratio = Math.max(0, Math.min(1, offsetX / rect.width))
          const newTime = Math.floor(ratio * _duration)

          this._currentTime = newTime
          const progress = ratio * 100

          this.setData({
            currentTime: this._formatTime(newTime),
            progress: progress
          })

          app.globalData.player.currentTime = newTime
          app.globalData.player.progress = progress
        })
      }
    },

    // 关闭
    onClose() {
      this._clearTimer()
      // 清理音频监听
      const store = app.globalData.player._store
      if (store && store.audioContext) {
        if (this._onTimeUpdate) store.audioContext.offTimeUpdate(this._onTimeUpdate)
        if (this._onEnded) store.audioContext.offEnded(this._onEnded)
      }
      this.triggerEvent('close')
    },

    // 返回上一页
    onBack() {
      this._clearTimer()
      // 清理音频监听
      const store = app.globalData.player._store
      if (store && store.audioContext) {
        if (this._onTimeUpdate) store.audioContext.offTimeUpdate(this._onTimeUpdate)
        if (this._onEnded) store.audioContext.offEnded(this._onEnded)
      }
      // 暂停播放
      if (store) {
        store.pause()
      }
      this.triggerEvent('back')
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
