#!/bin/bash
docker exec -i scheduler python - <<'PYEOF'
import httpx, subprocess
r = httpx.post("http://127.0.0.1:8002/admin/scripts",
    headers={"X-Role": "admin"},
    json={"name": "del_cleanup_test", "description": "", "type": "automation",
          "code": "print(1)", "visibility": "private", "cron": None, "enabled": False},
    timeout=30.0)
sid = r.json()["id"]
print("created id:", sid, "| command:", r.json()["command"])
d = httpx.delete(f"http://127.0.0.1:8002/admin/scripts/{sid}",
                 headers={"X-Role": "admin"}, timeout=30.0)
print("deleted:", d.status_code)
exists = subprocess.run(["ls", "/app/scripts/del_cleanup_test.py"], capture_output=True).returncode == 0
print("file exists after delete:", exists)
assert d.status_code == 200 and not exists, "cleanup check failed"
print("CLEANUP-OK")
PYEOF
