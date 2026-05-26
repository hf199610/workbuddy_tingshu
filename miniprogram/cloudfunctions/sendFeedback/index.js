// 云函数入口文件 - 意见反馈
const cloud = require('wx-server-sdk')
const nodemailer = require('nodemailer')

cloud.init({
  env: cloud.DYNAMIC_CURRENT_ENV
})

// 创建邮件发送器
function createTransporter() {
  return nodemailer.createTransport({
    host: process.env.MAIL_HOST || 'smtp.qq.com',
    port: parseInt(process.env.MAIL_PORT) || 587,
    secure: false,
    auth: {
      user: process.env.MAIL_USERNAME || '1365655586@qq.com',
      pass: process.env.MAIL_PASSWORD
    }
  })
}

// 云函数入口函数
exports.main = async (event, context) => {
  const { content, contact = '', userInfo = null } = event

  // 验证反馈内容
  if (!content || content.trim().length === 0) {
    return {
      success: false,
      error: '反馈内容不能为空'
    }
  }

  if (content.length > 2000) {
    return {
      success: false,
      error: '反馈内容过长，请控制在2000字以内'
    }
  }

  try {
    // 构建邮件内容
    const mailOptions = {
      from: `"听书金句小程序" <${process.env.MAIL_FROM || '1365655586@qq.com'}>`,
      to: process.env.MAIL_TO || '1365655586@qq.com',
      subject: `【意见反馈】来自 ${contact || '匿名用户'}`,
      text: `
来源：小程序意见反馈
联系方式：${contact || '未提供'}
用户信息：${userInfo ? JSON.stringify(userInfo) : '未登录'}

反馈内容：
${content}
      `.trim(),
      html: `
<h3>来源：小程序意见反馈</h3>
<p><strong>联系方式：</strong>${contact || '未提供'}</p>
<p><strong>用户信息：</strong>${userInfo ? JSON.stringify(userInfo) : '未登录'}</p>
<hr>
<h4>反馈内容：</h4>
<p>${content.replace(/\n/g, '<br>')}</p>
      `.trim()
    }

    // 发送邮件
    const transporter = createTransporter()
    await transporter.sendMail(mailOptions)

    return {
      success: true,
      message: '反馈已发送成功'
    }
  } catch (err) {
    console.error('发送邮件失败:', err)
    return {
      success: false,
      error: '发送失败: ' + err.message
    }
  }
}