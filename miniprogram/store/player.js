// store/player.js - 播放器状态管理（支持真实音频 + 字幕同步）
class PlayerStore {
  constructor() {
    this.isPlaying = false
    this.currentBook = null
    this.currentQuote = null
    this.progress = 0
    this.duration = 0
    this.audioContext = null
    this.subtitles = []       // 字幕数据 [{index, start, end, text}, ...]
    this.currentSubtitleIndex = -1  // 当前字幕索引
    this.listeners = []
  }

  init(audioContext) {
    this.audioContext = audioContext

    audioContext.onPlay(() => {
      this.isPlaying = true
      this.notifyListeners()
    })

    audioContext.onPause(() => {
      this.isPlaying = false
      this.notifyListeners()
    })

    audioContext.onStop(() => {
      this.isPlaying = false
      this.notifyListeners()
    })

    audioContext.onEnded(() => {
      this.isPlaying = false
      this.progress = 0
      this.currentSubtitleIndex = -1
      this.notifyListeners()
    })

    audioContext.onTimeUpdate(() => {
      this.progress = Math.floor(audioContext.currentTime)
      this.duration = Math.floor(audioContext.duration || 0)

      // 字幕同步：根据当前播放时间找到对应字幕
      this._updateSubtitleIndex(audioContext.currentTime)

      this.notifyListeners()
    })

    audioContext.onError((err) => {
      console.error('音频播放错误:', err)
      this.isPlaying = false
      // 给更明确的错误提示
      let errMsg = '音频播放失败'
      if (err && err.errMsg) {
        if (err.errMsg.includes('403')) {
          errMsg = '音频链接已过期，请刷新'
        } else if (err.errMsg.includes('decode')) {
          errMsg = '音频格式不支持'
        }
      }
      wx.showToast({ title: errMsg, icon: 'none' })
      this.notifyListeners()
    })
  }

  // 更新当前字幕索引
  _updateSubtitleIndex(currentTime) {
    if (!this.subtitles || this.subtitles.length === 0) return

    // 检查字幕是否有真实时间戳（非0）
    const hasRealTimestamps = this.subtitles.some(s => s.start > 0 || s.end > 0)

    if (!hasRealTimestamps) {
      // 无真实时间戳：按进度比例分配字幕
      const totalDuration = this.audioContext ? this.audioContext.duration : this._estimateDuration()
      if (totalDuration <= 0) return

      const progress = currentTime / totalDuration
      const subtitleIndex = Math.floor(progress * this.subtitles.length)
      const found = Math.min(subtitleIndex, this.subtitles.length - 1)

      if (found !== this.currentSubtitleIndex) {
        this.currentSubtitleIndex = found
      }
      return
    }

    // 有真实时间戳：使用二分查找
    let left = 0
    let right = this.subtitles.length - 1
    let found = -1

    while (left <= right) {
      const mid = Math.floor((left + right) / 2)
      const sub = this.subtitles[mid]

      if (currentTime >= sub.start && currentTime <= sub.end) {
        found = mid
        break
      } else if (currentTime < sub.start) {
        right = mid - 1
      } else {
        left = mid + 1
      }
    }

    // 如果没找到精确匹配，找到最近的已过字幕
    if (found === -1 && left > 0 && left <= this.subtitles.length) {
      const prev = this.subtitles[left - 1]
      if (currentTime >= prev.start) {
        found = left - 1
      }
    }

    if (found !== this.currentSubtitleIndex) {
      this.currentSubtitleIndex = found
    }
  }

  // 估算音频时长（当无法获取时使用）
  _estimateDuration() {
    // 假设平均语速：中文约 300字/分钟，即 5字/秒
    const textLength = this.currentBook ? this.currentBook.scriptLength || 0 : 0
    return textLength / 5
  }

  play(book) {
    this.currentBook = book
    // 支持 subtitles 或 sentences 字段
    this.subtitles = (book.subtitles || book.sentences || []).map((s, i) => ({
      index: i,
      start: s.startTime || s.start || 0,
      end: s.endTime || s.end || 0,
      text: s.text
    }))
    this.currentSubtitleIndex = -1

    if (this.audioContext) {
      // 如果有真实音频 URL，播放真实音频
      if (book.audioUrl && book.audioUrl.length > 0) {
        // 将 cloud:// 路径转换为临时URL
        this._convertCloudURL(book.audioUrl).then(url => {
          this.audioContext.src = url
          this.audioContext.title = book.title
          this.audioContext.episodeName = book.title + ' - 精华讲解'
          this.audioContext.singer = book.author || ''
          this.audioContext.coverImgUrl = book.coverUrl || ''
          this.audioContext.play()
          console.log('播放真实音频:', url)
        }).catch(err => {
          console.error('音频URL转换失败:', err)
          // 降级到模拟播放
          this.isPlaying = true
          this.notifyListeners()
        })
      } else {
        // 无音频 URL，保持模拟模式（不设置 src，仅更新状态）
        console.log('无音频URL，模拟播放模式')
        this.isPlaying = true
        this.notifyListeners()
      }
    } else {
      this.isPlaying = true
      this.notifyListeners()
    }
  }

  // 将云存储路径转换为临时URL
  async _convertCloudURL(audioUrl) {
    // 如果不是云存储路径，直接返回
    if (!audioUrl || !audioUrl.startsWith('cloud://')) {
      return audioUrl
    }

    // 获取临时URL
    const fileID = audioUrl.replace('cloud://', '')
    try {
      const res = await wx.cloud.getTempFileURL({
        fileList: [fileID]
      })

      if (res.fileList && res.fileList[0]) {
        const fileData = res.fileList[0]
        if (fileData.status === 0) {
          return fileData.tempFileURL
        } else {
          throw new Error(fileData.errMsg || '获取临时URL失败')
        }
      }
      throw new Error('无文件数据')
    } catch (err) {
      console.error('getTempFileURL 失败:', err)
      // 如果转换失败，返回原路径，让播放器自然报错
      return audioUrl
    }
  }

  pause() {
    if (this.audioContext) {
      this.audioContext.pause()
    }
    this.isPlaying = false
    this.notifyListeners()
  }

  // 从当前位置继续播放
  resume() {
    if (!this.currentBook) return

    if (this.audioContext) {
      if (this.audioContext.paused) {
        this.audioContext.play()
      }
      this.isPlaying = true
      this.notifyListeners()
    } else {
      this.isPlaying = true
      this.notifyListeners()
    }
  }

  toggle() {
    if (this.isPlaying) {
      this.pause()
    } else {
      this.play(this.currentBook)
    }
  }

  seek(position) {
    if (this.audioContext) {
      this.audioContext.seek(position)
    }
    // 更新字幕索引
    this._updateSubtitleIndex(position)
    this.notifyListeners()
  }

  // 获取格式化的播放数据（供 UI 使用）
  getPlayData() {
    return {
      isPlaying: this.isPlaying,
      currentBook: this.currentBook,
      progress: this.progress,
      duration: this.duration,
      subtitles: this.subtitles,
      currentSubtitleIndex: this.currentSubtitleIndex,
      hasAudio: !!(this.currentBook && this.currentBook.audioUrl),
    }
  }

  addListener(callback) {
    this.listeners.push(callback)
  }

  removeListener(callback) {
    this.listeners = this.listeners.filter(cb => cb !== callback)
  }

  notifyListeners() {
    const data = this.getPlayData()
    this.listeners.forEach(cb => cb(data))
  }
}

module.exports = PlayerStore
