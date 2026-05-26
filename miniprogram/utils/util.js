// utils/util.js - 工具函数

/**
 * 格式化时间（秒 → MM:SS）
 */
function formatTime(seconds) {
  const mins = Math.floor(seconds / 60)
  const secs = seconds % 60
  return `${padZero(mins)}:${padZero(secs)}`
}

function padZero(num) {
  return num < 10 ? '0' + num : '' + num
}

/**
 * 格式化日期
 */
function formatDate(date) {
  const d = new Date(date)
  const year = d.getFullYear()
  const month = padZero(d.getMonth() + 1)
  const day = padZero(d.getDate())
  return `${year}-${month}-${day}`
}

/**
 * 节流函数
 */
function throttle(fn, delay = 300) {
  let timer = null
  return function(...args) {
    if (timer) return
    timer = setTimeout(() => {
      fn.apply(this, args)
      timer = null
    }, delay)
  }
}

/**
 * 防抖函数
 */
function debounce(fn, delay = 300) {
  let timer = null
  return function(...args) {
    clearTimeout(timer)
    timer = setTimeout(() => {
      fn.apply(this, args)
    }, delay)
  }
}

module.exports = {
  formatTime,
  formatDate,
  throttle,
  debounce
}
