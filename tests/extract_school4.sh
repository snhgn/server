#!/bin/bash
echo 1 | sudo -S rm -rf /tmp/school
python3 - <<'PYEOF'
import zipfile, os, shutil
src = '/tmp/school.zip'
dst = '/tmp/school'
os.makedirs(dst, exist_ok=True)
zf = zipfile.ZipFile(src)
count = 0
for info in zf.infolist():
    raw = info.filename
    try:
        name = raw.encode('cp437').decode('gbk')
    except Exception:
        try:
            name = raw.encode('cp437').decode('utf-8')
        except Exception:
            name = raw
    # zip 内路径分隔符可能是反斜杠，统一转成 /
    name = name.replace('\\', '/')
    if name.endswith('/'):
        os.makedirs(os.path.join(dst, name), exist_ok=True)
        continue
    target = os.path.join(dst, name)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with zf.open(info) as srcf, open(target, 'wb') as dstf:
        shutil.copyfileobj(srcf, dstf)
    count += 1
zf.close()
print('extracted files:', count)
PYEOF
echo "=== 结构 ==="
echo 1 | sudo -S ls /tmp/school/
