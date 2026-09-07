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
PROBE_TARGETS = [
    ("http://connect.rom.miui.com/generate_204", 204),
    ("http://cp.cloudflare.com/generate_204", 204),
    ("http://www.baidu.com", None),
    ("http://www.qq.com", None),
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


def is_online(timeout: int = 5) -> bool:
    """检测公网是否在线。

    - 只要有任一探针明确检测到门户劫持，立即返回 False；
    - 探针正常返回则判定为 True；
    - 所有探针均连接失败则判定为 False。
    """
    online_hits = 0
    for url, expected in PROBE_TARGETS:
        res = _probe_single(url, expected, timeout)
        if res is False:
            # 明确被劫持
            return False
        if res is True:
            online_hits += 1
            if online_hits >= 1:
                return True
    return False


if __name__ == "__main__":
    print("is_online():", is_online())
