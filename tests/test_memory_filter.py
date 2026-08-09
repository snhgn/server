"""MemoryTagFilter 逻辑单元测试：验证标签过滤 + 跨 chunk 提取 + 健壮性"""
import re

_MEMORY_OPEN_RE = re.compile(r'<(?P<tag>memory_delete|memory)\b(?P<attrs>[^>]*)>')
_ATTR_RE = re.compile(r'([\w-]+)\s*=\s*"([^"]*)"')
_CLOSE_MEM_RE = re.compile(r'</memory\s*>')
_CLOSE_MEMDEL_RE = re.compile(r'</memory_delete\s*>')


def _extract_memory_ops(text):
    ops = []
    clean_parts = []
    pos = 0
    i = 0
    n = len(text)
    while i < n:
        m = _MEMORY_OPEN_RE.search(text, i)
        if not m:
            break
        tag = m.group("tag")
        attrs_raw = m.group("attrs").strip()
        self_close = attrs_raw.endswith("/")
        if self_close:
            attrs_raw = attrs_raw[:-1].rstrip()
        attrs = {k: v for k, v in _ATTR_RE.findall(attrs_raw)}
        cat = attrs.get("category", "")
        key = attrs.get("key", "")
        if not (cat and key):
            i = m.end()
            continue
        if tag == "memory_delete":
            if self_close:
                clean_parts.append(text[pos:m.start()])
                ops.append(("delete", cat, key, ""))
                pos = m.end()
                i = m.end()
            else:
                close = _CLOSE_MEMDEL_RE.search(text, m.end())
                if not close:
                    break
                clean_parts.append(text[pos:m.start()])
                ops.append(("delete", cat, key, ""))
                pos = close.end()
                i = close.end()
        else:
            if self_close:
                clean_parts.append(text[pos:m.start()])
                pos = m.end()
                i = m.end()
                continue
            close = _CLOSE_MEM_RE.search(text, m.end())
            if not close:
                break
            val = text[m.end():close.start()].strip()
            clean_parts.append(text[pos:m.start()])
            ops.append(("add", cat, key, val))
            pos = close.end()
            i = close.end()
    clean_parts.append(text[pos:])
    return "".join(clean_parts), ops


class MemoryTagFilter:
    def __init__(self):
        self._buf = ""
        self.ops = []

    def feed(self, chunk):
        self._buf += chunk
        clean, ops = _extract_memory_ops(self._buf)
        self.ops.extend(ops)
        keep = 0
        m = _MEMORY_OPEN_RE.search(clean)
        if m:
            keep = len(clean) - m.start()
        else:
            pm = re.search(r'</?[A-Za-z][^>]*$', clean)
            if pm:
                keep = len(clean) - pm.start()
        if keep:
            out, self._buf = clean[:-keep], clean[-keep:]
        else:
            out, self._buf = clean, ""
        return out

    def finish(self):
        clean, ops = _extract_memory_ops(self._buf)
        self.ops.extend(ops)
        self._buf = ""
        m = _MEMORY_OPEN_RE.search(clean)
        if m:
            clean = clean[: m.start()]
        else:
            pm = re.search(r'</?[A-Za-z][^>]*$', clean)
            if pm:
                clean = clean[: pm.start()]
        return clean


def run_case(name, chunks, expected_visible, expected_ops):
    f = MemoryTagFilter()
    out = ""
    for c in chunks:
        out += f.feed(c)
    out += f.finish()
    ok = out == expected_visible and f.ops == expected_ops
    print(f"{'PASS' if ok else 'FAIL'}: {name}")
    if not ok:
        print(f"  visible={out!r} expected={expected_visible!r}")
        print(f"  ops={f.ops!r} expected={expected_ops!r}")
    return ok


all_ok = True

# 1. 单 chunk 内写
all_ok &= run_case("single write", ['你好<memory category="偏好" key="语言">Python</memory>'],
                   "你好", [("add", "偏好", "语言", "Python")])

# 2. 跨 chunk 写
all_ok &= run_case("write across chunks", ['你好，<memory category="', '偏好" key="名字">', '小明</memory>再见'],
                   "你好，再见", [("add", "偏好", "名字", "小明")])

# 3. 删除自闭合
all_ok &= run_case("delete self-closed", ['旧信息已删除<memory_delete category="知识" key="旧"/>完了'],
                   "旧信息已删除完了", [("delete", "知识", "旧", "")])

# 4. 删除显式闭合
all_ok &= run_case("delete explicit-close", ['A<memory_delete category="知识" key="旧"></memory_delete>B'],
                   "AB", [("delete", "知识", "旧", "")])

# 5. 属性顺序调换（key 在前）
all_ok &= run_case("attr order swapped", ['x<memory key="k1" category="c1">v1</memory>y'],
                   "xy", [("add", "c1", "k1", "v1")])

# 6. 属性间换行
all_ok &= run_case("attr newline", ['<memory category="偏好"\n key="名字">小明</memory>'],
                   "", [("add", "偏好", "名字", "小明")])

# 7. 无标签正常文本
all_ok &= run_case("no tag", ["普通回答内容，", "分两段"], "普通回答内容，分两段", [])

# 8. 多标签混合
all_ok &= run_case("multiple tags", ['A<memory category="c1" key="k1">v1</memory>B<memory_delete category="c2" key="k2"/>C'],
                   "ABC", [("add", "c1", "k1", "v1"), ("delete", "c2", "k2", "")])

# 9. 值含中文和括号
all_ok &= run_case("value content", ['<memory category="项目" key="项目名">ST32 电机(调试中)</memory>回答'],
                   "回答", [("add", "项目", "项目名", "ST32 电机(调试中)")])

# 10. 未闭合标签在流式中被保留，最后 finish 丢弃不泄漏
f = MemoryTagFilter()
out = f.feed("正常文本<memory category=\"偏好\" key=\"半")
out2 = f.feed("途断掉")
tail = f.finish()
ok = out + out2 + tail == "正常文本" and f.ops == []
print(f"{'PASS' if ok else 'FAIL'}: unfinished tag dropped")
if not ok:
    print(f"  visible={out!r}+{out2!r}+{tail!r} ops={f.ops!r}")
all_ok &= ok

# 11. 纯记忆指令（无可见文本）也能提取
all_ok &= run_case("only memory tag", ['<memory category="偏好" key="语言">Python</memory>'],
                   "", [("add", "偏好", "语言", "Python")])

# 12. 纯删除指令
all_ok &= run_case("only delete tag", ['<memory_delete category="偏好" key="语言"/>'],
                   "", [("delete", "偏好", "语言", "")])

# 13. 长值跨多个 chunk 不泄漏
f = MemoryTagFilter()
out = ""
for c in ['<memory category="偏好" key="长值">' + "A" * 200 + '</memory>结束']:
    out += f.feed(c)
out += f.finish()
ok = out == "结束" and f.ops == [("add", "偏好", "长值", "A" * 200)]
print(f"{'PASS' if ok else 'FAIL'}: long value")
if not ok:
    print(f"  visible_len={len(out)} ops={f.ops!r}")
all_ok &= ok

print("\n" + ("ALL PASS" if all_ok else "SOME FAILED"))
