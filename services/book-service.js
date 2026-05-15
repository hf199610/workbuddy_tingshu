// services/book-service.js - 书籍服务
const mockData = require('../mock/books.js')

class BookService {
  // 获取所有书籍
  getBooks(categoryId = 0) {
    let books = mockData.books
    
    if (categoryId > 0) {
      books = books.filter(b => b.category === categoryId)
    }
    
    return books
  }
  
  // 根据ID获取书籍
  getBookById(id) {
    return mockData.books.find(b => b.id === id)
  }
  
  // 获取热门书籍
  getHotBooks(limit = 3) {
    return mockData.books.filter(b => b.featured).slice(0, limit)
  }
  
  // 获取最新书籍
  getLatestBooks(limit = 6) {
    return mockData.books.slice(0, limit)
  }
  
  // 搜索书籍
  searchBooks(keyword) {
    return mockData.books.filter(b => 
      b.title.includes(keyword) || b.author.includes(keyword)
    )
  }
}

module.exports = new BookService()
