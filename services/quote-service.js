// services/quote-service.js - 金句服务
const mockData = require('../mock/quotes.js')

class QuoteService {
  // 获取所有金句
  getQuotes() {
    return mockData.quotes
  }
  
  // 根据书籍ID获取金句
  getQuotesByBookId(bookId) {
    return mockData.quotes.filter(q => q.bookId === bookId)
  }
  
  // 获取随机金句
  getRandomQuote(excludeId = null) {
    let quotes = mockData.quotes
    if (excludeId) {
      quotes = quotes.filter(q => q.id !== excludeId)
    }
    const index = Math.floor(Math.random() * quotes.length)
    return quotes[index]
  }
  
  // 搜索金句
  searchQuotes(keyword) {
    return mockData.quotes.filter(q =>
      q.content.includes(keyword) || q.author.includes(keyword) || q.bookName.includes(keyword)
    )
  }
}

module.exports = new QuoteService()
