#!/bin/bash
# AI 脚本生成链路验证:generate(AI编写) -> review(另一个AI审查) -> create(落盘) -> run -> 清理
set -e

echo "== [1] generate:提示词 -> AI 编写代码 =="
docker exec scheduler python - <<'PYEOF'
import httpx
r = httpx.post("http://127.0.0.1:8002/admin/scripts/generate",
    headers={"X-Role": "admin"},
    json={"name": "aigen_selftest",
          "prompt": "访问 https://www.baidu.com 首页,HTTP 200 且页面包含'百度'输出 BAIDU-OK,否则 exit 1;30 秒超时,失败重试 2 次"},
    timeout=115.0)
d = r.json()
print("  status:", r.status_code)
print("  generator:", d.get("generator"))
print("  syntax_ok:", d.get("syntax_ok"), d.get("syntax_error"))
print("  code_len:", len(d.get("code", "")))
assert r.status_code == 200 and d.get("code"), f"FAIL: {d}"
open("/tmp/gen_code.py", "w").write(d["code"])
print("  PASS")
PYEOF

echo "== [2] review:另一个 AI 交叉审查 =="
docker exec scheduler python - <<'PYEOF'
import httpx, json
code = open("/tmp/gen_code.py").read()
r = httpx.post("http://127.0.0.1:8002/admin/scripts/review",
    headers={"X-Role": "admin"},
    json={"code": code, "name": "aigen_selftest", "description": "百度可达性检测"},
    timeout=115.0)
d = r.json()
print("  status:", r.status_code)
print("  verdict:", d.get("verdict"), "| reviewer:", d.get("reviewer"))
print("  issues:", json.dumps(d.get("issues", []), ensure_ascii=False))
print("  summary:", (d.get("summary") or "")[:120])
assert r.status_code == 200, f"FAIL: {d}"
print("  PASS")
PYEOF

echo "== [3] create:code 落盘并自动生成 command =="
docker exec scheduler python - <<'PYEOF'
import httpx
code = open("/tmp/gen_code.py").read()
r = httpx.post("http://127.0.0.1:8002/admin/scripts",
    headers={"X-Role": "admin"},
    json={"name": "aigen_selftest", "description": "AI 生成链路自测", "type": "automation",
          "code": code, "visibility": "private", "cron": None, "enabled": False},
    timeout=30.0)
d = r.json()
print("  status:", r.status_code)
print("  command:", d.get("command"))
assert r.status_code == 201, f"FAIL: {d}"
open("/tmp/sid", "w").write(str(d["id"]))
print("  PASS (id=%s)" % d["id"])
PYEOF

echo "== [4] run:实际执行 AI 生成的脚本 =="
docker exec scheduler python - <<'PYEOF'
import httpx, time
sid = open("/tmp/sid").read().strip()
r = httpx.post(f"http://127.0.0.1:8002/admin/scripts/{sid}/run",
               headers={"X-Role": "admin"}, timeout=30.0)
print("  run:", r.status_code, r.json())
time.sleep(10)
s = httpx.get(f"http://127.0.0.1:8002/admin/scripts/{sid}/summary",
              headers={"X-Role": "admin"}, timeout=30.0).json()
last = s["recent_runs"][0] if s["recent_runs"] else {}
print("  last_run status:", last.get("status"))
print("  output:", (last.get("output") or "")[:200].replace("\n", " | "))
assert last.get("status") == "success", f"FAIL: {last}"
print("  PASS")
PYEOF

echo "== [5] 验证落盘文件 =="
docker exec scheduler sh -c 'ls -l /app/scripts/aigen_selftest.py && head -3 /app/scripts/aigen_selftest.py'

echo "== [6] 清理测试脚本 =="
docker exec scheduler python - <<'PYEOF'
import httpx
sid = open("/tmp/sid").read().strip()
r = httpx.delete(f"http://127.0.0.1:8002/admin/scripts/{sid}",
                 headers={"X-Role": "admin"}, timeout=30.0)
print("  delete:", r.status_code, r.json())
PYEOF

echo "ALL-VERIFIED"
