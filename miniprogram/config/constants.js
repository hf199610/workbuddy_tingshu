// config/constants.js - 公共常量配置

// 分类映射（统一管理，避免多处重复定义）
const CATEGORIES = {
  1: '经典名著',
  2: '科幻小说',
  3: '历史文学',
  4: '哲学思考',
  5: '商业经济',
  6: '心理励志',
  7: '散文随笔'
}

// 分类列表（用于筛选栏）
const CATEGORY_LIST = [
  { id: 0, name: '全部' },
  { id: 1, name: '经典名著' },
  { id: 2, name: '科幻小说' },
  { id: 3, name: '历史文学' },
  { id: 4, name: '哲学思考' },
  { id: 5, name: '商业经济' },
  { id: 6, name: '心理励志' },
  { id: 7, name: '散文随笔' }
]

module.exports = {
  CATEGORIES,
  CATEGORY_LIST
}
