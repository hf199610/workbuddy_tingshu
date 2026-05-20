/**
 * 云函数上传脚本
 * 使用方法:
 *   node upload_cloudfunctions.js
 *
 * 需要先确保已登录腾讯云:
 *   1. 运行 tcb login 进行交互式登录
 *   2. 或者使用 SecretID/SecretKey: tcb login --apiKeyId xxx --apiKey yyy
 *   3. 或者在微信开发者工具中手动上传
 */

const { execSync } = require('child_process')
const fs = require('fs')
const path = require('path')

// 云函数目录
const CLOUD_FUNCTIONS_DIR = path.join(__dirname, 'miniprogram', 'cloudfunctions')

// 需要上传的云函数列表
const FUNCTIONS = [
  'searchBooks',
  'searchQuotes',
  'getBooks',
  'getQuotes',
  'getBookDetail',
  'batchImportBooks'
]

// 云开发环境ID（从 app.js 中获取）
const ENV_ID = 'cloud1-d2ggs9k1bf3aa2a18'

console.log('=== 云函数上传脚本 ===\n')
console.log('环境ID:', ENV_ID)
console.log('')

// 检查登录状态
try {
  execSync('npx tcb user', { stdio: 'pipe', encoding: 'utf-8' })
} catch (e) {
  console.log('⚠️  未检测到登录状态，请先登录:')
  console.log('')
  console.log('  方法1（推荐）: 运行以下命令扫码登录')
  console.log('    npx tcb login')
  console.log('')
  console.log('  方法2: 在微信开发者工具中手动上传:')
  console.log('    1. 打开微信开发者工具')
  console.log('    2. 展开 cloudfunctions/ 目录')
  console.log('    3. 右键点击云函数文件夹')
  console.log('    4. 选择 "上传并部署：云端安装依赖"')
  console.log('')
  process.exit(1)
}

// 检查云函数目录
if (!fs.existsSync(CLOUD_FUNCTIONS_DIR)) {
  console.error('❌ 云函数目录不存在:', CLOUD_FUNCTIONS_DIR)
  process.exit(1)
}

// 上传每个云函数
async function uploadFunctions() {
  for (const funcName of FUNCTIONS) {
    const funcDir = path.join(CLOUD_FUNCTIONS_DIR, funcName)

    if (!fs.existsSync(funcDir)) {
      console.log(`⚠️  云函数 ${funcName} 目录不存在，跳过`)
      continue
    }

    console.log(`📤 上传云函数: ${funcName}...`)

    try {
      // 使用 tcb CLI 上传
      execSync(`npx tcb fn deploy ${funcName} --path ${funcDir} -e ${ENV_ID}`, {
        cwd: path.join(__dirname, 'miniprogram'),
        stdio: 'inherit'
      })
      console.log(`✅ 云函数 ${funcName} 上传成功!\n`)
    } catch (err) {
      // 如果 tcb 不可用，尝试使用微信开发者工具的 CLI
      try {
        const wechatDevToolsPath = 'C:\\Program Files (x86)\\Tencent\\微信webdevtools\\1.06.2308290\\cli'

        if (fs.existsSync(path.join(wechatDevToolsPath, 'bat'))) {
          execSync(`"${wechatDevToolsPath}/cli" uploadCloudFunction -t ${funcName} -d ${CLOUD_FUNCTIONS_DIR}`, {
            stdio: 'inherit'
          })
          console.log(`✅ 云函数 ${funcName} 上传成功!\n`)
        } else {
          throw new Error('微信开发者工具 CLI 不存在')
        }
      } catch (err2) {
        console.error(`❌ 云函数 ${funcName} 上传失败:`, err.message)
        console.log('💡 请在微信开发者工具中手动上传:\n')
        console.log(`   1. 展开 cloudfunctions/${funcName} 目录`)
        console.log(`   2. 右键点击 ${funcName} 文件夹`)
        console.log(`   3. 选择 "上传并部署：云端安装依赖"\n`)
      }
    }
  }

  console.log('=== 上传完成 ===')
}

uploadFunctions()