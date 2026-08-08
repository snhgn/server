#!/bin/bash
echo "=== Gateway logs ==="
docker logs gateway --tail 10 2>&1
echo
echo "=== Socket check ==="
docker exec gateway ls -la /var/run/docker.sock 2>&1
echo
echo "=== Docker API test ==="
docker exec gateway python3 -c "
import httpx
try:
    r = httpx.get('http://localhost/v1.24/containers/json',
                  transport=httpx.HTTPTransport(uds='/var/run/docker.sock'),
                  timeout=5)
    print('Status:', r.status_code)
    data = r.json()
    print('Containers:', len(data))
    for c in data:
        print(' -', c.get('Names', ['?'])[0], c.get('Status', ''))
except Exception as e:
    print('Error:', type(e).__name__, str(e))
" 2>&1
