// store/player.js - 播放器状态管理
class PlayerStore {
  constructor() {
    this.isPlaying = false
    this.currentBook = null
    this.currentQuote = null
    this.progress = 0
    this.duration = 0
    this.audioContext = null
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
    
    audioContext.onEnded(() => {
      this.isPlaying = false
      this.progress = 0
      this.notifyListeners()
    })
    
    audioContext.onTimeUpdate(() => {
      this.progress = Math.floor(audioContext.currentTime)
      this.duration = Math.floor(audioContext.duration)
      this.notifyListeners()
    })
  }
  
  play(book) {
    this.currentBook = book
    if (this.audioContext) {
      this.audioContext.src = '' // 这里应该设置为真实的音频URL
      this.audioContext.title = book.title
      this.audioContext.play()
    }
    this.isPlaying = true
    this.notifyListeners()
  }
  
  pause() {
    if (this.audioContext) {
      this.audioContext.pause()
    }
    this.isPlaying = false
    this.notifyListeners()
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
  }
  
  addListener(callback) {
    this.listeners.push(callback)
  }
  
  removeListener(callback) {
    this.listeners = this.listeners.filter(cb => cb !== callback)
  }
  
  notifyListeners() {
    const data = {
      isPlaying: this.isPlaying,
      currentBook: this.currentBook,
      progress: this.progress,
      duration: this.duration
    }
    this.listeners.forEach(cb => cb(data))
  }
}

module.exports = PlayerStore
