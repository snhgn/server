# -*- coding: utf-8 -*-
"""教务系统已登录会话池（仅进程内存，绝不落盘）。

强智教务的 JSESSIONID 在服务端会维持较长时间，而原实现每次抓取都重新走
一遍「取验证码 → 识别 → 取 scode#sxh → 提交登录」四跳握手，课表 / 成绩 /
考试 / 培养方案 / 等级考试各自为战，同一个学生在一次使用中要重复过多次
验证码。这里把已登录的 requests.Session 按学号暂存复用，把重复的验证码
识别成本降到零（预期省掉 ~80% 的验证码往返）。

安全约束（与 schedule/service.py 保持一致）：
- 会话与凭据只存在于进程内存，绝不落盘、绝不写日志；
- 同一学号的会话互斥检出，requests.Session 不跨线程并发使用；
- TTL 到期 / 探测发现已被踢下线 / 使用中抛异常时立即丢弃并释放连接。

并发说明：槽位 (_Slot) 与其互斥锁同生共死，淘汰时整槽移除。极端情况下
（某学号槽位正在被淘汰的瞬间）同一学号可能短暂出现两个槽位，后果仅为多
做一次登录，不会产生共享 Session 的并发访问。
"""
import contextlib
import threading
import time
from typing import Callable, Iterator, Optional, Tuple

from . import captcha

# 已登录会话的可复用时长。强智会话服务端超时远大于此，15 分钟足够覆盖
# 一次典型的「打开课表页 → 依次点成绩/考试/教室」使用过程。
SESSION_TTL = 900.0  # 15 分钟

# 静置超过这个秒数才做「是否被踢下线」探针。探针本身要拉一次课表页（实测
# ~186ms），而用户连续点几个工具箱按钮时每次都探针会把收益吃掉（实测探针占
# 考试查询总耗时的 86%）。刚用过不到一分钟的会话几乎不可能刚好失效，跳过探针；
# 静置较久的会话仍要探，避免拿到静默的空结果。
PROBE_AFTER_IDLE = 60.0

# 池容量上限。访客路径允许任意学号，必须有界，防止无界增长。
MAX_SLOTS = 64

_SLOTS: dict = {}
_GUARD = threading.Lock()


class _Slot:
    """单个学号的池槽位：互斥锁 + 当前可复用的已登录会话。"""

    __slots__ = ("lock", "session", "ts")

    def __init__(self):
        self.lock = threading.Lock()
        self.session = None  # type: Optional[object]
        self.ts = 0.0


class LoginFailed(ValueError):
    """自动登录失败（账号密码错误 / 验证码始终识别不出）。

    继承 ValueError 是为了兼容既有调用方按 ValueError 捕获的约定
    （routers/schedule.py 里所有工具箱路由都是 except ValueError -> 400），
    同时让能区分「登录失败」与「抓取解析出错」的调用方改用本类型精确捕获。
    """


def _slot_for(key: str) -> _Slot:
    """取得（或创建）某学号的槽位。调用方必须随后 acquire 其 lock。"""
    with _GUARD:
        slot = _SLOTS.get(key)
        if slot is None:
            if len(_SLOTS) >= MAX_SLOTS:
                # 淘汰最老的未占用槽位；全部占用则临时超限，下一轮再回收
                for k, s in sorted(_SLOTS.items(), key=lambda kv: kv[1].ts):
                    if not s.lock.locked():
                        _discard_session(s.session)
                        del _SLOTS[k]
                        break
            slot = _SLOTS[key] = _Slot()
        return slot


def _discard_session(session) -> None:
    if session is None:
        return
    try:
        session.close()
    except Exception:
        pass


def is_alive(session, probe: Optional[Callable] = None) -> bool:
    """探测池中会话是否仍然有效。

    探测失败（网络异常）时按有效处理：此时重新登录同样会失败，而盲目
    丢弃健康的会话会白白浪费一次验证码。真正的失效会在使用时暴露，由
    session_for 的异常分支丢弃。
    """
    if probe is None:
        return True
    try:
        return bool(probe(session))
    except Exception:
        return True


def default_probe(session) -> bool:
    """默认探针：拉一次课表页，判断是否被踢回登录页。

    强智在会话失效时不返回 302，而是直接吐登录页 HTML，所以只能靠内容
    特征判断。已登录的课表页本身就是接下来要抓的数据，这个探测是顺手的。
    """
    html = captcha.get_timetable(session)
    return not captcha.is_login_page(html)


@contextlib.contextmanager
def session_for(student_id: str, password: str, max_retry: int = 5,
                verbose: bool = False,
                probe: Optional[Callable] = None) -> Iterator[Tuple[object, bool]]:
    """借出一个已登录的教务会话，用完自动归还。

    产出 (session, reused)：reused=True 表示命中池中已有会话、跳过了登录。
    会话在整个 with 块内被该学号独占；块内抛异常则丢弃该会话（可能已被
    服务端作废），正常结束则归还池中等待复用。

    probe 传入时**只在会话静置超过 PROBE_AFTER_IDLE 才真正执行** —— 探针要
    拉一次课表页（约 186ms），连续操作时每次都探会抵消会话池的收益。
    """
    key = (student_id or "").strip()
    if not key:
        raise LoginFailed("请输入学号")

    slot = _slot_for(key)
    slot.lock.acquire()
    try:
        pooled = slot.session
        idle = (time.monotonic() - slot.ts) if pooled is not None else None
        need_probe = probe is not None and (idle is None or idle > PROBE_AFTER_IDLE)
        if pooled is not None and idle is not None and idle < SESSION_TTL \
                and is_alive(pooled, probe if need_probe else None):
            session, reused = pooled, True
        else:
            _discard_session(pooled)
            slot.session = None
            ok, session, reason = captcha.login(
                key, password, max_retry=max_retry, verbose=verbose)
            if not ok:
                raise LoginFailed(reason or "账号或密码错误或验证码识别失败")
            reused = False

        # 独占：移出池中，避免同一学号的并发请求共享同一个 Session
        slot.session = None
        healthy = True
        try:
            yield session, reused
        except BaseException:
            healthy = False
            raise
        finally:
            if healthy:
                slot.session = session
                slot.ts = time.monotonic()
            else:
                _discard_session(session)
    finally:
        slot.lock.release()


def invalidate(student_id: str) -> None:
    """主动作废某学号的池中会话（如发现响应是登录页时）。"""
    key = (student_id or "").strip()
    if not key:
        return
    with _GUARD:
        slot = _SLOTS.get(key)
        if slot is not None and not slot.lock.locked():
            _discard_session(slot.session)
            slot.session = None
            slot.ts = 0.0


def stats() -> dict:
    """管理端可观测信息：只含槽位数量，不含任何会话内容或凭据。"""
    with _GUARD:
        now = time.monotonic()
        live = sum(1 for s in _SLOTS.values()
                   if s.session is not None and now - s.ts < SESSION_TTL)
        return {"slots": len(_SLOTS), "reusable_sessions": live,
                "ttl_seconds": SESSION_TTL}
