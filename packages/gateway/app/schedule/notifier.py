# -*- coding: utf-8 -*-
"""课表与成绩监控邮件通知模块。

通过 SMTP SSL 发送测试邮件与出分通知。
"""
import logging
import re
import smtplib
from datetime import datetime
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr

from ..config import settings

logger = logging.getLogger("gateway.schedule.notifier")

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validate_email_address(email: str) -> bool:
    """验证邮箱格式基本有效性。"""
    if not email:
        return False
    return bool(EMAIL_REGEX.match(email.strip()))


def send_test_grade_monitor_email(to_email: str, student_id: str = "") -> tuple[bool, str]:
    """发送成绩出分监控配置验证/测试邮件。

    Returns:
        (success: bool, message: str)
    """
    to_email = to_email.strip()
    if not validate_email_address(to_email):
        return False, "邮箱地址格式无效，请检查"

    host = settings.SMTP_HOST
    port = settings.SMTP_PORT
    sender = settings.SMTP_SENDER
    auth_code = settings.SMTP_AUTH_CODE

    if not (host and sender and auth_code):
        logger.error("SMTP 邮件配置不完整")
        return False, "服务器邮件配置不完整，请联系管理员"

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    subject = "【北林课表】成绩出分监控配置成功 - 测试邮件"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = Header(subject, "utf-8")
    msg["From"] = formataddr((str(Header("北林课表 · 出分监控", "utf-8")), sender))
    msg["To"] = to_email

    text_content = f"""同学，您好！

您已成功开启北林教务系统的【成绩出分监控】服务。这是一封系统自动发送的测试验证邮件，收到本邮件表明您的邮箱设置正确，通知链路畅通！

- 监控学号：{student_id or '当前绑定学号'}
- 接收邮箱：{to_email}
- 监控状态：监控已生效
- 测试时间：{now_str}

温馨提示：后台将在出分季定期自动巡检教务系统。一旦发现有新学期或新课程成绩发布，系统将在第一时间向本邮箱发送成绩出分详情与绩点提醒。祝您期末考试取得优异成绩！

本邮件由 snhgn.me 课表系统自动发出，无需回复。
"""

    html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', 'Segoe UI', Roboto, sans-serif; background-color: #f4f5f7; margin: 0; padding: 20px; color: #1f2937; }}
  .container {{ max-width: 560px; margin: 0 auto; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.05); border: 1px solid #e5e7eb; }}
  .header {{ background: #111827; padding: 24px 20px; text-align: center; color: #ffffff; }}
  .header h1 {{ margin: 0; font-size: 18px; font-weight: 600; letter-spacing: 0.5px; }}
  .header p {{ margin: 6px 0 0; font-size: 12px; color: #9ca3af; font-family: monospace; }}
  .content {{ padding: 24px 20px; }}
  .greeting {{ font-size: 15px; font-weight: 600; margin-bottom: 12px; color: #111827; }}
  .desc {{ font-size: 13px; line-height: 1.6; color: #4b5563; margin-bottom: 20px; }}
  .card {{ background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 8px; padding: 14px 16px; margin-bottom: 20px; }}
  .item {{ display: flex; justify-content: space-between; font-size: 13px; padding: 6px 0; border-bottom: 1px dashed #e5e7eb; }}
  .item:last-child {{ border-bottom: none; }}
  .item-label {{ color: #6b7280; }}
  .item-value {{ color: #111827; font-weight: 500; font-family: monospace; }}
  .tip {{ font-size: 12px; line-height: 1.6; color: #374151; background: #eff6ff; border-left: 3px solid #3b82f6; padding: 10px 14px; border-radius: 4px; }}
  .footer {{ text-align: center; padding: 14px 20px; font-size: 11px; color: #9ca3af; border-top: 1px solid #f3f4f6; background: #fafafa; }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>北林课表 · 成绩出分监控</h1>
    <p>Grade Monitor Service Notification</p>
  </div>
  <div class="content">
    <div class="greeting">同学，您好！</div>
    <div class="desc">
      您已成功开启北林教务系统的<strong>【成绩出分监控】</strong>服务。这是一封系统自动发送的测试验证邮件，收到本邮件表明您的邮箱设置正确，通知链路畅通！
    </div>
    <div class="card">
      <div class="item"><span class="item-label">监控学号</span><span class="item-value">{student_id or '当前绑定学号'}</span></div>
      <div class="item"><span class="item-label">接收邮箱</span><span class="item-value">{to_email}</span></div>
      <div class="item"><span class="item-label">监控状态</span><span class="item-value" style="color: #059669; font-weight: 600;">● 监控已生效</span></div>
      <div class="item"><span class="item-label">测试时间</span><span class="item-value">{now_str}</span></div>
    </div>
    <div class="tip">
      💡 <strong>温馨提示：</strong>后台将在出分季定期自动巡检教务系统。一旦发现有新学期或新课程成绩发布，系统将在第一时间向本邮箱发送成绩出分详情与绩点提醒。祝您期末考试取得优异成绩！
    </div>
  </div>
  <div class="footer">
    本邮件由 snhgn.me 课表系统自动发出，无需回复。
  </div>
</div>
</body>
</html>
"""

    msg.attach(MIMEText(text_content, "plain", "utf-8"))
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    try:
        with smtplib.SMTP_SSL(host, port, timeout=15) as server:
            server.login(sender, auth_code)
            server.sendmail(sender, [to_email], msg.as_string())
        logger.info("成绩监控测试邮件发送成功 -> %s (student_id=%s)", to_email, student_id)
        return True, f"测试邮件已成功发送至 {to_email}"
    except (smtplib.SMTPException, OSError) as e:
        logger.warning("成绩监控测试邮件发送失败 -> %s: %s", to_email, e)
        return False, f"邮件发送失败: {e}"
