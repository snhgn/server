import urllib.request
import json

headers = {
    "Content-Type": "application/json",
    "X-User-Id": "1",
    "X-Username": "admin",
    "X-Role": "admin",
}

print("=== 1. Testing ai-service /api/settings ===")
req = urllib.request.Request("http://127.0.0.1:8000/api/settings", headers=headers)
with urllib.request.urlopen(req, timeout=10) as resp:
    print("Settings response:", resp.read().decode())

print("\n=== 2. Testing ai-service /api/chat with Gemini (gemini-3.7-flash) ===")
payload = json.dumps({"message": "请回复'Gemini 3.7 测试成功'这一句话。", "provider": "gemini"}).encode("utf-8")
req = urllib.request.Request("http://127.0.0.1:8000/api/chat", data=payload, headers=headers)
try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        res = json.loads(resp.read().decode())
        print("Gemini response success:", res.get("success"), "provider:", res.get("provider"))
        print("Gemini answer:", res.get("answer"))
except Exception as e:
    print("Gemini error:", e)

print("\n=== 3. Testing ai-service /api/chat with GLM ===")
payload = json.dumps({"message": "请回复'GLM 测试成功'这一句话。", "provider": "glm"}).encode("utf-8")
req = urllib.request.Request("http://127.0.0.1:8000/api/chat", data=payload, headers=headers)
try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        res = json.loads(resp.read().decode())
        print("GLM response success:", res.get("success"), "provider:", res.get("provider"))
        print("GLM answer:", res.get("answer"))
except Exception as e:
    print("GLM error:", e)
