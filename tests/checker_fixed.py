"""网络连通性与校园网认证门户检测。

思路：
1. 强制使用 IPv4 直连探测公网端点（因为校园网未认证时仅 IPv4 出站被劫持，IPv6 可能直通导致误判）；
2. 探测 204 状态端点（如 miui / cloudflare / gstatic generate_204）：
   - 正常联网时返回 HTTP 204 No Content；
   - 被 Dr.COM 门户劫持时会返回 HTTP 200/302 伴随 HTML/JS 跳转页面，特征极明显；
3. 探测常规 HTTP 端点（如 baidu.com / qq.com）：
   - 检查 HTTP 状态码、Location 重定向头、以及返回 HTML body；
   - 识别 Dr.COM 典型的 JS 跳转 (<script>location.href="http://10.1.1.10/a79.htm...")、
     "Authentication is required"、"login.bjfu.edu.cn"、"10.1.1.10" 等劫持标记；
4. 命中劫持标记立即判定为离线（False），触发自动重登。
5. 没有劫持标记时按**多数派**汇总：至少 3 个探针明确可达，且可达数严格多于
   无法判定的探针数。单靠个别探针不足以证明出网正常——校园网网关会给少数
   端点透明应答，实测断网时仍有探针返回 204（详见 MIN_ONLINE_HITS 注释）。
"""
import http.client
import socket
from urllib.parse import urlparse

# 命中这些特征说明被 Dr.COM / 校园网认证网关劫持
PORTAL_MARKERS = (
    "login.bjfu.edu.cn",
    "10.1.1.10",
    "a79.htm",
    "authentication is required",
    "上网登录页",
    "校园信息化",
    "dr.com",
    "drcom",
    "eportal",
    "location.href",
)

# 探测目标列表：(URL, 期望状态码/None)
# 204 探测极为精准：未认证劫持返回 200 带 HTML，正常返回 204 无内容
#
# 端点是实测挑的（2026-10-02，健康校园网下的单次响应耗时）：
#   connect.rom.miui.com/generate_204  0.07s
#   cp.cloudflare.com/generate_204     0.38s   隧道依赖 Cloudflare，必须保留
#   www.baidu.com                      0.15s
#   www.qq.com                         0.13s
#   mirrors.aliyun.com                 0.16s   国内镜像，校园网内友好
#   www.163.com                        0.17s
# 已排除 www.bing.com(8.13s) 与 cn.bing.com(6.50s)：常态响应就接近超时上限，
# 会把"慢"误报成"断"。探针越多，单个探针故障越不影响整体判定；但总数越多
# 整体判定越慢，所以只保留这 6 个实测快速、且分布在不同服务商的端点。
PROBE_TARGETS = [
    ("http://connect.rom.miui.com/generate_204", 204),
    ("http://cp.cloudflare.com/generate_204", 204),
    ("http://www.baidu.com", None),
    ("http://www.qq.com", None),
    ("http://mirrors.aliyun.com", None),
    ("http://www.163.com", None),
]


def _resolve_ipv4(host: str) -> list:
    """仅解析 IPv4 A 记录，避免 IPv6 逃逸导致漏检。"""
    try:
        infos = socket.getaddrinfo(host, 80, socket.AF_INET, socket.SOCK_STREAM)
        return [i[4][0] for i in infos]
    except OSError:
        return []


def _contains_portal_markers(text: str) -> bool:
    if not text:
        return False
    t = text.lower()
    return any(m in t for m in PORTAL_MARKERS)


def _probe_single(url: str, expected_status: int or None, timeout: int):
    """探测单个 URL。

    返回:
      True: 网络正常（已连通且未被劫持）
      False: 确认离线（命中门户劫持标记）
      None: 无法连接 / 超时 / DNS 失败
    """
    u = urlparse(url)
    host = u.hostname
    port = u.port or 80
    path = u.path or "/"

    ips = _resolve_ipv4(host)
    if not ips:
        return None

    for ip in ips:
        conn = None
        try:
            conn = http.client.HTTPConnection(ip, port, timeout=timeout)
            conn.request(
                "GET",
                path,
                headers={
                    "Host": host,
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Connection": "close",
                },
            )
            resp = conn.getresponse()
            code = resp.status
            loc = resp.getheader("Location") or ""
            body_bytes = resp.read(2048)
            body_text = body_bytes.decode("utf-8", errors="ignore")

            # 1. 检查 Location 重定向头是否指向门户
            if _contains_portal_markers(loc):
                return False

            # 2. 检查 body 是否包含门户劫持标记
            if _contains_portal_markers(body_text):
                return False

            # 3. 针对 204 探针：期望 204，若返回 200 则多半被劫持渲染了登录页
            if expected_status == 204:
                if code == 204:
                    return True
                # 非 204 但返回了 200/302，说明被网关拦截
                return False

            # 4. 常规探针：200-399 且无任何劫持标记
            if 200 <= code < 400:
                return True

            return None
        except (OSError, http.client.HTTPException):
            continue
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass
    return None


# 判定"在线"所需的最小命中数：6 个探针里至少 3 个明确可达，
# 且命中数必须严格多于"无法判定"数。
#
# 为什么不能沿用"任意一个探针通过就算在线"（原 online_hits >= 1 即 return True）：
# 校园网网关会对少数探测端点做透明应答（例如缓存 generate_204 并回 204），
# 于是在**实际完全断网**的情况下仍有探针返回正常。
# 2026-10-02 的真实故障：connect.rom.miui.com/generate_204 与 www.qq.com
# 判定为 True，而 baidu / cloudflare 全部连接失败、github 与 baidu 的 TLS
# 握手全部超时。按旧逻辑 is_online() 返回 True，bjfu-login 自愈循环于是每
# 60 秒记一条"网络正常，无需认证"，永远不去登录门户，snhgn.me 持续返回 530。
MIN_ONLINE_HITS = 3


def judge_online(results) -> bool:
    """把各探针的判定汇总成整体在线结论。

    results 的元素含义与 ``_probe_single`` 的返回值一致：
      ``False`` -> 命中门户劫持证据（确定离线）
      ``True``  -> 该端点明确可达且未被劫持
      ``None``  -> 连接失败/超时，无法判定（既不算在线，也不算离线证据）

    判定规则：
      1. 只要出现 ``False``（门户劫持）即离线；
      2. 命中数需达到 ``MIN_ONLINE_HITS``；
      3. 命中数需严格多于无法判定数，避免"少数探针侥幸通过"被当成健康。
    """
    if any(r is False for r in results):
        return False
    hits = sum(1 for r in results if r is True)
    unknown = sum(1 for r in results if r is None)
    return hits >= MIN_ONLINE_HITS and hits > unknown


def is_online(timeout: int = 5) -> bool:
    """检测公网是否在线。

    - 任一探针命中门户劫持证据，立即返回 False（不再给其它探针翻案的机会）；
    - 否则汇总全部探针，由 judge_online 按多数派规则判定；
    - 探针全部连接失败时视为离线，触发自愈登录。
    """
    results = []
    for url, expected in PROBE_TARGETS:
        res = _probe_single(url, expected, timeout)
        if res is False:
            # 明确被劫持
            return False
        results.append(res)
    return judge_online(results)


if __name__ == "__main__":
    print("is_online():", is_online())
