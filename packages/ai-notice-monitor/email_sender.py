"""
email_sender.py - SMTP 邮件发送模块

职责：
1. 支持 QQ / 163 邮箱（SSL 465，授权码认证）
2. 生成 HTML 格式邮件：今日新增数量 + 每条通知详情
3. 邮件包含：标题 / 摘要 / 重要程度 / 截止时间 / 原文链接
"""
from __future__ import annotations

import html as html_lib
import logging
import smtplib
from datetime import date
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr

from ai_summary import NoticeSummary
from config import EmailConfig
from scraper import Notice

logger = logging.getLogger(__name__)

# 重要程度 → 颜色
_IMPORTANCE_COLOR = {
    "high": "#d9534f",
    "medium": "#f0ad4e",
    "low": "#5bc0de",
}


class EmailSenderError(Exception):
    """邮件发送失败统一异常。"""


class EmailSender:
    """SMTP 邮件发送器。"""

    def __init__(self, config: EmailConfig) -> None:
        self.config = config
        if not (config.smtp_host and config.sender_email and config.auth_code and config.receiver_email):
            raise ValueError("邮件配置不完整：请检查 .env 中 SMTP_HOST/SMTP_SENDER/SMTP_AUTH_CODE/SMTP_RECEIVER")

    def send_daily_digest(self, items: list[tuple[Notice, NoticeSummary]]) -> None:
        """
        发送每日通知摘要邮件。

        items: [(Notice, NoticeSummary), ...] 当日新增通知及其摘要
        """
        if not items:
            logger.info("无新增通知，跳过发送")
            return
        subject = f"[校园通知] {date.today().isoformat()} 新增 {len(items)} 条通知"
        body_html = self._build_html(items)
        self._send(subject, body_html)
        logger.info("邮件已发送: %s 条通知 -> %s", len(items), self.config.receiver_email)

    def send_empty_report(self, total_scanned: int, total_db: int, sites: list[str]) -> None:
        """
        发送无新通知时的日常巡检汇报邮件。
        """
        subject = f"[校园通知] {date.today().isoformat()} 今日无新增通知（监控正常运行）"
        body_html = self._build_empty_html(total_scanned, total_db, sites)
        self._send(subject, body_html)
        logger.info("巡检说明邮件已发送 -> %s", self.config.receiver_email)

    # ---------- 邮件内容 ----------

    def _build_empty_html(self, total_scanned: int, total_db: int, sites: list[str]) -> str:
        """构造无新通知时的 HTML 报告正文。"""
        sites_list_html = "".join(
            f'<li style="margin: 4px 0; color: #555;">{html_lib.escape(s)}</li>'
            for s in sites
        )
        return f"""
        <html>
        <body style="font-family:'PingFang SC','Microsoft YaHei',Arial,sans-serif;background:#f7f6f2;padding:24px 12px;margin:0;">
          <div style="max-width:600px;margin:0 auto;background:#ffffff;border-radius:10px;border:1px solid #e8e5de;box-shadow:0 2px 10px rgba(0,0,0,0.03);overflow:hidden;">
            <!-- Header -->
            <div style="background:#161719;padding:22px 24px;border-bottom:3px solid #f5b738;">
              <h2 style="margin:0;color:#f2f2f2;font-size:17px;letter-spacing:0.04em;">
                北京林业大学 · 校园通知监控
              </h2>
              <p style="margin:6px 0 0;color:#8e9399;font-size:12px;font-family:monospace;">
                snhgn· Notice Monitor · Daily Heartbeat
              </p>
            </div>

            <!-- Body Content -->
            <div style="padding:24px;">
              <div style="display:inline-block;background:rgba(16,185,129,0.1);color:#059669;border:1px solid rgba(16,185,129,0.3);padding:4px 12px;border-radius:20px;font-size:12px;font-weight:500;margin-bottom:16px;">
                ● 今日巡检正常 · 无新增通知
              </div>

              <p style="font-size:14px;color:#333;line-height:1.7;margin:0 0 16px;">
                监控系统已于 <b>{date.today().isoformat()}</b> 完成对各官方站点的自动抓取与去重比对，各站点暂无新发布的内容（可能处于假期或非工作日更新周期）。
              </p>

              <!-- Stats Table -->
              <div style="background:#fcfbf9;border:1px solid #eee;border-radius:8px;padding:14px;margin-bottom:18px;">
                <table style="width:100%;font-size:13px;color:#444;border-collapse:collapse;">
                  <tr>
                    <td style="padding:6px 0;color:#777;">巡检时间</td>
                    <td style="padding:6px 0;text-align:right;font-family:monospace;color:#111;">{date.today().isoformat()} 09:00</td>
                  </tr>
                  <tr>
                    <td style="padding:6px 0;color:#777;border-top:1px dashed #eee;">扫描有效条目</td>
                    <td style="padding:6px 0;text-align:right;font-family:monospace;color:#111;">{total_scanned} 条</td>
                  </tr>
                  <tr>
                    <td style="padding:6px 0;color:#777;border-top:1px dashed #eee;">今日新增通知</td>
                    <td style="padding:6px 0;text-align:right;font-family:monospace;color:#059669;font-weight:bold;">0 条</td>
                  </tr>
                  <tr>
                    <td style="padding:6px 0;color:#777;border-top:1px dashed #eee;">库中累计归档</td>
                    <td style="padding:6px 0;text-align:right;font-family:monospace;color:#111;">{total_db} 条</td>
                  </tr>
                  <tr>
                    <td style="padding:6px 0;color:#777;border-top:1px dashed #eee;">监控覆盖站点</td>
                    <td style="padding:6px 0;text-align:right;color:#111;">{len(sites)} 个专区</td>
                  </tr>
                </table>
              </div>

              <!-- Sites Monitored -->
              <div style="font-size:12.5px;color:#666;margin-bottom:14px;">
                <b style="color:#333;">已覆盖站点清单：</b>
                <ul style="margin:6px 0 0;padding-left:20px;font-size:12px;">
                  {sites_list_html}
                </ul>
              </div>

              <p style="font-size:12px;color:#888;margin:16px 0 0;border-top:1px solid #eee;padding-top:12px;line-height:1.6;">
                如后续站点发布新通知，系统将在第一时间进行 AI 智能提炼并通过邮件推送。<br>
                <em>Stay curious, keep building. · snhgn·</em>
              </p>
            </div>
          </div>
        </body>
        </html>
        """

    def _build_html(self, items: list[tuple[Notice, NoticeSummary]]) -> str:
        """构造 HTML 邮件正文。"""
        cards = []
        for notice, summary in items:
            color = _IMPORTANCE_COLOR.get(summary.importance, "#5bc0de")
            importance_text = {
                "high": "高",
                "medium": "中",
                "low": "低",
            }.get(summary.importance, summary.importance)
            cards.append(
                f"""
                <div style="border:1px solid #eee;border-radius:8px;padding:14px;margin-bottom:12px;
                            border-left:4px solid {color};">
                  <h3 style="margin:0 0 8px;font-size:15px;">
                    <a href="{html_lib.escape(notice.url)}" style="color:#2b6cb0;text-decoration:none;">
                      {html_lib.escape(notice.title)}
                    </a>
                  </h3>
                  <table style="font-size:13px;color:#444;">
                    <tr><td style="padding:2px 8px 2px 0;">来源</td>
                        <td><span style="background:#eef2f7;color:#555;padding:1px 8px;border-radius:3px;font-size:12px;">
                          {html_lib.escape(notice.source or '-')}
                        </span></td></tr>
                    <tr><td style="padding:2px 8px 2px 0;">重要程度</td><td>
                        <span style="background:{color};color:#fff;padding:1px 8px;border-radius:3px;font-size:12px;">
                          {importance_text}
                        </span></td></tr>
                    <tr><td style="padding:2px 8px 2px 0;">分类</td>
                        <td>{html_lib.escape(summary.category)}</td></tr>
                    <tr><td style="padding:2px 8px 2px 0;">发布时间</td>
                        <td>{html_lib.escape(notice.publish_time or '-')}</td></tr>
                    <tr><td style="padding:2px 8px 2px 0;">截止时间</td>
                        <td>{html_lib.escape(summary.deadline or '-')}</td></tr>
                    <tr><td style="padding:2px 8px 2px 0;vertical-align:top;">摘要</td>
                        <td>{html_lib.escape(summary.summary or '（AI 摘要不可用）')}</td></tr>
                    <tr><td style="padding:2px 8px 2px 0;vertical-align:top;">建议行动</td>
                        <td>{html_lib.escape(summary.action or '-')}</td></tr>
                    <tr><td style="padding:2px 8px 2px 0;">原文</td>
                        <td><a href="{html_lib.escape(notice.url)}">查看原文</a></td></tr>
                  </table>
                </div>
                """
            )
        return f"""
        <html>
        <body style="font-family:'Microsoft YaHei',Arial,sans-serif;background:#f7f7f7;padding:16px;">
          <div style="max-width:640px;margin:0 auto;background:#fff;border-radius:8px;padding:20px;">
            <h2 style="margin:0 0 6px;font-size:18px;">北京林业大学理学院 · 通知公告</h2>
            <p style="color:#888;font-size:13px;margin:0 0 16px;">
              {date.today().isoformat()} 共发现 <b style="color:#d9534f;">{len(items)}</b> 条新通知
            </p>
            {"".join(cards)}
            <p style="color:#aaa;font-size:12px;border-top:1px solid #eee;padding-top:10px;margin-top:16px;">
              本邮件由「校园通知智能监控系统」自动生成。
            </p>
          </div>
        </body>
        </html>
        """

    # ---------- SMTP 发送 ----------

    def _send(self, subject: str, body_html: str) -> None:
        """通过 SMTP SSL 发送邮件。"""
        msg = MIMEMultipart("alternative")
        msg["From"] = formataddr((str(Header("校园通知监控", "utf-8")), self.config.sender_email))
        msg["To"] = self.config.receiver_email
        msg["Subject"] = Header(subject, "utf-8")
        msg.attach(MIMEText(body_html, "html", "utf-8"))

        try:
            with smtplib.SMTP_SSL(self.config.smtp_host, self.config.smtp_port, timeout=30) as server:
                server.login(self.config.sender_email, self.config.auth_code)
                server.sendmail(self.config.sender_email, [self.config.receiver_email], msg.as_string())
        except (smtplib.SMTPException, OSError) as e:
            raise EmailSenderError(f"SMTP 发送失败: {e}") from e
