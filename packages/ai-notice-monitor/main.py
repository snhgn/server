"""
main.py - 校园通知智能监控系统主入口

流程：
    读取配置 → 抓取通知列表 → 去重入库 → 新通知 AI 摘要 → 邮件发送 → 结束

命令行用法：
    python main.py           # 正常执行一次完整流程
    python main.py --test    # 测试模式：只抓取+摘要，不发送邮件，不发真实网络请求到邮箱
    python main.py --dry-run # 干跑：抓取+入库+摘要，跳过邮件发送
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime

from ai_summary import AISummarizer, SummaryError
from config import BASE_DIR, load_config
from database import NoticeDatabase
from email_sender import EmailSender, EmailSenderError
from scraper import Notice, NoticeScraper

# 日志格式：时间 级别 模块: 信息
# 日志文件固定写到脚本目录，避免 CWD 变化导致日志丢失（容器内 CWD 为 /app）
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(str(BASE_DIR / "notice_monitor.log"), encoding="utf-8"),
    ],
)
logger = logging.getLogger("main")


def run(config=None, *, dry_run: bool = False, test_mode: bool = False) -> int:
    """
    执行完整监控流程。

    dry_run: 不发送邮件
    test_mode: 不发邮件 + 仅打印（供调试）
    返回：本次新增通知数（0 表示无新增）
    """
    if config is None:
        config = load_config()

    # ---- 1. 初始化组件 ----
    scraper = NoticeScraper(config.scraper, config.sites)
    db = NoticeDatabase(config.database)
    try:
        # 记录本次运行前的库大小，用于首次运行判断
        db_count_before = db.count()

        # ---- 2. 抓取各站点通知列表（合并去重）----
        notices = scraper.fetch_all()
        logger.info("列表解析完成，共 %d 条", len(notices))

        # ---- 3. 去重：找出本次新增 ----
        new_notices: list[Notice] = []
        for n in notices:
            is_new = db.insert_new(n)
            if is_new:
                new_notices.append(n)
                logger.info("新增通知: [%s] %s (%s)", n.source, n.title, n.url)

        logger.info("本次新增 %d 条，库中总计 %d 条", len(new_notices), db.count())

        if not new_notices:
            logger.info("没有新通知，结束")
            return 0

        # 首次运行（运行前库为空）且 FIRST_RUN_SEND_ALL=false → 历史只入库不发送
        if db_count_before == 0 and not config.run.first_run_send_all:
            logger.info("首次运行模式：历史通知已入库，本次不发送（后续新通知才会发邮件）")
            return len(new_notices)

        # ---- 4. AI 摘要 ----
        summarizer = AISummarizer(config.ai)
        digest: list[tuple[Notice, object]] = []
        for n in new_notices:
            try:
                detail = scraper.fetch_detail_text(n.url)
                summary = summarizer.summarize(n.title, detail)
                logger.info("摘要完成 [%s] %s: %s", summary.importance, n.title, summary.summary)
            except (SummaryError, Exception) as e:
                # AI 摘要失败不阻塞：用空摘要降级，仍发送
                logger.error("摘要失败 %s: %s，使用降级摘要", n.title, e)
                summary = _fallback_summary(n)
            digest.append((n, summary))

        # ---- 5. 发送邮件 ----
        if dry_run or test_mode:
            mode = "dry-run" if dry_run else "test"
            logger.info("[%s] 跳过邮件发送，本次待发送 %d 条", mode, len(digest))
            if test_mode:
                _print_digest(digest)
            return len(new_notices)

        email_sender = EmailSender(config.email)
        email_sender.send_daily_digest(digest)  # type: ignore[arg-type]

        # ---- 6. 标记已发送 ----
        for n, _ in digest:
            db.mark_sent(n)
        logger.info("完成：发送 %d 条通知", len(digest))
        return len(new_notices)
    finally:
        db.close()


def _fallback_summary(notice: Notice) -> object:
    """AI 不可用时构造降级摘要对象。"""
    from ai_summary import NoticeSummary

    return NoticeSummary(
        title=notice.title,
        category="其他",
        importance="medium",
        deadline="",
        summary="（AI 摘要不可用）",
        action="请点击原文查看",
    )


def _print_digest(digest: list[tuple[Notice, object]]) -> None:
    """测试模式下打印摘要结果。"""
    for i, (n, s) in enumerate(digest, 1):
        d = getattr(s, "to_dict", lambda: {"summary": str(s)})()
        print(f"\n[{i}] {n.title}")
        print(f"    链接: {n.url}")
        print(f"    时间: {n.publish_time}")
        for k, v in d.items():
            print(f"    {k}: {v}")


def main() -> None:
    """命令行入口。"""
    parser = argparse.ArgumentParser(description="校园通知智能监控系统")
    parser.add_argument("--test", action="store_true", help="测试模式：抓取+摘要，不发邮件，打印结果")
    parser.add_argument("--dry-run", action="store_true", help="干跑：抓取+入库+摘要，不发邮件")
    args = parser.parse_args()

    logger.info("======== 校园通知监控开始 %s ========", datetime.now().isoformat(timespec="seconds"))
    try:
        run(dry_run=args.dry_run, test_mode=args.test)
    except EmailSenderError as e:
        logger.error("邮件发送失败：%s", e)
        sys.exit(2)
    except Exception as e:  # 兜底：任何未处理异常不静默
        logger.exception("运行失败：%s", e)
        sys.exit(1)
    logger.info("======== 运行结束 ========")


if __name__ == "__main__":
    main()
