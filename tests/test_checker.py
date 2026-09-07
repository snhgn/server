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


if __name__ == "__main__":
    unittest.main()
