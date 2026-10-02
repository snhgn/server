import unittest
from unittest.mock import MagicMock, patch
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import checker_fixed as checker


class TestChecker(unittest.TestCase):
    def test_contains_portal_markers(self):
        # 1. 之前导致线上误判的真实 Dr.COM 响应体
        drcom_html = (
            '<html><head><script type="text/javascript">'
            'location.href="http://10.1.1.10/a79.htm?usermac=3C-A0-67-20-01-A0&userip=172.28.204.98&ssid=bjfu%2Dwifi%2Doffice&acip=10%2E26%2E4%2E253"'
            '</script></head><body>Authentication is required.</body></html>'
        )
        self.assertTrue(checker._contains_portal_markers(drcom_html))
        self.assertTrue(checker._contains_portal_markers("http://login.bjfu.edu.cn/"))
        self.assertTrue(checker._contains_portal_markers("上网登录页"))
        self.assertFalse(checker._contains_portal_markers("<!DOCTYPE html><html><head><title>Baidu</title></head></html>"))

    @patch("checker_fixed._resolve_ipv4", return_value=["1.2.3.4"])
    @patch("http.client.HTTPConnection")
    def test_drcom_hijack_detected_as_offline(self, mock_conn_cls, mock_resolve):
        # 模拟 Dr.COM 拦截常规 HTTP 返回 200 OK + JS 跳转 HTML
        mock_conn = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.getheader.return_value = None
        drcom_body = b'<html><script>location.href="http://10.1.1.10/a79.htm?usermac=..."</script><body>Authentication is required.</body></html>'
        mock_resp.read.return_value = drcom_body
        mock_conn.getresponse.return_value = mock_resp
        mock_conn_cls.return_value = mock_conn

        res = checker._probe_single("http://www.baidu.com", None, timeout=2)
        self.assertFalse(res)  # 必须判定为离线

    @patch("checker_fixed._resolve_ipv4", return_value=["1.2.3.4"])
    @patch("http.client.HTTPConnection")
    def test_204_probe_hijack_detected(self, mock_conn_cls, mock_resolve):
        # 204 探针被拦截返回 200
        mock_conn = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.getheader.return_value = None
        mock_resp.read.return_value = b'<html>login</html>'
        mock_conn.getresponse.return_value = mock_resp
        mock_conn_cls.return_value = mock_conn

        res = checker._probe_single("http://connect.rom.miui.com/generate_204", 204, timeout=2)
        self.assertFalse(res)

    @patch("checker_fixed._resolve_ipv4", return_value=["1.2.3.4"])
    @patch("http.client.HTTPConnection")
    def test_204_probe_normal_online(self, mock_conn_cls, mock_resolve):
        # 204 探针正常返回 204 No Content
        mock_conn = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status = 204
        mock_resp.getheader.return_value = None
        mock_resp.read.return_value = b''
        mock_conn.getresponse.return_value = mock_resp
        mock_conn_cls.return_value = mock_conn

        res = checker._probe_single("http://connect.rom.miui.com/generate_204", 204, timeout=2)
        self.assertTrue(res)


class TestJudgeOnline(unittest.TestCase):
    """judge_online 的多数派判定，回归 2026-10-02 的真实误判故障。"""

    def test_incident_pattern_is_offline(self):
        # 当天实测：miui 与 qq 判定 True，cloudflare/baidu 连接失败。
        # 旧逻辑"任意一个通过即在线"在这里返回 True，导致自愈循环永不登录门户、
        # 站点持续 530。必须判为离线。
        self.assertFalse(checker.judge_online([True, None, None, True]))
        # 若新增的阿里云/网易探针同样失败
        self.assertFalse(checker.judge_online([True, None, None, True, None, None]))

    def test_two_flaky_probes_still_counts_as_online(self):
        # 有意保留的容忍度：多数派成立（4 通过 / 2 不确定）仍判在线，
        # 免得个别探针偶发慢就把好好的网络判成断网、触发多余的重登与隧道重启。
        self.assertTrue(checker.judge_online([True, None, None, True, True, True]))

    def test_all_online_is_online(self):
        self.assertTrue(checker.judge_online([True] * len(checker.PROBE_TARGETS)))

    def test_all_unknown_is_offline(self):
        self.assertFalse(checker.judge_online([None] * len(checker.PROBE_TARGETS)))

    def test_portal_hijack_forces_offline(self):
        # 只要有一个探针命中劫持标记，无论其它探针多正常都判离线
        self.assertFalse(checker.judge_online([False] + [True] * 5))

    def test_majority_boundary(self):
        # 6 探针：4 通过 / 2 不确定 -> 在线（容忍两个探针故障）
        self.assertTrue(checker.judge_online([True] * 4 + [None] * 2))
        # 6 探针：3 通过 / 3 不确定 -> 不确定不算在线
        self.assertFalse(checker.judge_online([True] * 3 + [None] * 3))
        # 命中数低于 MIN_ONLINE_HITS 一律离线
        self.assertFalse(checker.judge_online([True, True, None, None, None, None]))

    def test_min_online_hits_is_covered_by_probe_count(self):
        # 阈值不能高到即使全部探针在线也判不出来
        self.assertLessEqual(checker.MIN_ONLINE_HITS, len(checker.PROBE_TARGETS))

    def test_probe_targets_are_distinct(self):
        urls = [u for u, _ in checker.PROBE_TARGETS]
        self.assertEqual(len(urls), len(set(urls)))


if __name__ == "__main__":
    unittest.main()
