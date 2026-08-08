# -*- coding: utf-8 -*-
"""解析教务系统课表 HTML，生成文字说明。

用法：
    py parse_timetable.py                 解析本地 timetable.html（若为空自动登录换学期抓取）
    py parse_timetable.py --probe         只打印页面结构与学期选项，不解析课表
    py parse_timetable.py --fetch         登录后自动轮询各学期直到拿到有课表的学期
"""
import argparse
import html
import os
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HTML_FILE = os.path.join(BASE_DIR, "timetable.html")
OUT_FILE = os.path.join(BASE_DIR, "timetable_parsed.txt")


def strip_tags(s):
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"\s+", " ", s)
    return html.unescape(s).strip()


# 强智课表节次块按行固定顺序渲染，服务端丢了连字符（如 "12节"）。
# 注意末尾还有一个 "第12节" 行，其 th 文本同为 "12节"，与首行撞车，
# 因此必须按行顺序而非文本映射。
PERIOD_SEQ = ["第1-2节", "第3-4节", "第5节", "第6-7节",
              "第8-9节", "第10-11节", "第12节"]
PERIOD_RANK = {v: i for i, v in enumerate(PERIOD_SEQ)}
PERIOD_RANK["第10-12节"] = PERIOD_RANK["第10-11节"]


def extract_selects(html):
    """提取页面里所有 <select> 的 name 与选项列表。"""
    selects = {}
    for m in re.finditer(r"<select\b[^>]*>.*?</select>", html, re.S):
        seg = m.group(0)
        name = re.search(r'name="([^"]*)"', seg)
        if not name:
            continue
        opts = re.findall(r'<option[^>]*value="([^"]*)"[^>]*>(.*?)</option>', seg, re.S)
        selects[name.group(1)] = [(v, strip_tags(t)) for v, t in opts]
    return selects


def probe(html):
    """打印页面结构：标题、学期/周次选项、表格首行。"""
    title = re.search(r"<title>([^<]*)</title>", html)
    print("标题:", strip_tags(title.group(1)) if title else "?")
    selects = extract_selects(html)
    for name, opts in selects.items():
        print(f"下拉框 {name}:")
        for v, t in opts:
            print(f"    {v} -> {t}")
    # 表格骨架
    m = re.search(r'<table[^>]*class="[^"]*Nsb_table[^"]*"[^>]*>(.*?)</table>', html, re.S)
    if m:
        cells = [strip_tags(c) for c in re.findall(r"<th[^>]*>(.*?)</th>", m.group(1), re.S)]
        print("表头:", cells)
    msg = re.search(r"alert\('([^']*)'\)", html)
    if msg:
        print("页面提示:", msg.group(1))


SEP_RE = re.compile(r"-{6,}")  # 单元格内多门课的分隔线


def _parse_block(b):
    """解析单个课程的 HTML 片段 -> 课程 dict。"""
    fields = {m.group(1): m.group(2).strip() for m in re.finditer(
        r"<font title='([^']*)'>(.*?)</font>", b, re.S)}
    lines = [strip_tags(x) for x in re.split(r"<br\s*/?>", b)]
    lines = [x for x in lines if x]
    if not lines:
        return None
    return {
        "name": lines[0],
        "teacher": fields.get("老师", ""),
        "weeks": fields.get("周次(节次)", ""),
        "room": fields.get("教室", ""),
    }


def _parse_cell(cell):
    """解析一个单元格（某天某节次），返回课程列表。

    单元格含两个 div：kbcontent1(简版) 与 kbcontent(详版，带老师)，
    优先取详版；每个 div 内可能有多门课，以 ------- 分隔线隔开。
    """
    detail = re.findall(
        r'<div[^>]*class="[^"]*kbcontent"[^>]*>(.*?)</div>', cell, re.S)
    brief = re.findall(
        r'<div[^>]*class="[^"]*kbcontent1"[^>]*>(.*?)</div>', cell, re.S)
    out = []
    for d in detail or brief:
        for part in SEP_RE.split(d):
            c = _parse_block(part)
            if c:
                out.append(c)
    return out


def parse_grid(html):
    """解析课表主网格，返回课程记录列表。

    强智 xskb_list 结构：每行一个节次块（12节/34节/5节...），每列一个星期；
    节次名由服务端渲染时丢了连字符，按 PERIOD_MAP 归一化。
    """
    m = re.search(
        r'<table[^>]*class="[^"]*Nsb_table[^"]*"[^>]*>(.*?)</table>', html, re.S
    )
    if not m:
        return []
    course_rows = []
    period_idx = 0
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", m.group(1), re.S):
        ths = re.findall(r"<th[^>]*>(.*?)</th>", tr, re.S)
        tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
        if not ths or len(tds) < 7:
            continue
        # 节次行按出现顺序取 PERIOD_SEQ，超长时回退到文本原样
        pname = (PERIOD_SEQ[period_idx]
                 if period_idx < len(PERIOD_SEQ) else strip_tags(ths[0]))
        period_idx += 1
        for day_idx, cell in enumerate(tds[:7], start=1):
            for c in _parse_cell(cell):
                c.update({"day": day_idx, "period": pname})
                course_rows.append(c)
    return course_rows


def merge_adjacent(course_rows):
    """合并 "第10-11节" 与 "第12节" 完全相同的课程（同一门课 10-12 节连排）。

    强智把 10-12 节拆成 "1011节" 与 "12节" 两行渲染，两行内容相同，
    合并后显示为 "第10-12节"，避免重复。按天配对，兼容每格多门课。
    """
    by_day = {}
    for c in course_rows:
        by_day.setdefault(c["day"], []).append(c)
    merged = []
    for day in sorted(by_day):
        rows = sorted(by_day[day],
                      key=lambda c: PERIOD_RANK.get(c["period"], 99))
        tail = [c for c in rows if c["period"] == "第12节"]
        taken = [False] * len(tail)
        for c in rows:
            if c["period"] != "第10-11节":
                continue
            key = (c["name"], c["teacher"], c["weeks"], c["room"])
            for i, t in enumerate(tail):
                if (not taken[i]
                        and (t["name"], t["teacher"], t["weeks"], t["room"]) == key):
                    c["period"] = "第10-12节"
                    taken[i] = True
                    break
        for c in rows:
            if c["period"] != "第12节":
                merged.append(c)
        for i, t in enumerate(tail):
            if not taken[i]:
                merged.append(t)
    return merged


def format_text(course_rows):
    """生成人类可读的课表文字，按星期与节次排序。"""
    days = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    out = []
    for c in merge_adjacent(course_rows):
        parts = [f"{days[c['day'] - 1]} {c['period']}", c["name"]]
        for k in ("weeks", "room", "teacher"):
            if c[k]:
                parts.append(c[k])
        out.append((c["day"], PERIOD_RANK.get(c["period"], 99), " | ".join(parts)))
    out.sort(key=lambda x: (x[0], x[1]))
    return "\n".join(line for _, _, line in out)


def fetch_semester(session, xnxq01id, zc=""):
    """抓取指定学期课表 HTML。"""
    import captcha as cap
    data = {"xnxq01id": xnxq01id}
    if zc:
        data["zc"] = zc
    r = session.post(cap.BASE_URL + "/jsxsd/xskb/xskb_list.do", data=data, timeout=15)
    r.encoding = "utf-8"
    return r.text


def main():
    parser = argparse.ArgumentParser(description="解析课表 HTML 生成文字说明")
    parser.add_argument("--probe", action="store_true", help="只打印页面结构")
    parser.add_argument("--fetch", action="store_true", help="登录后轮询各学期")
    args = parser.parse_args()

    if args.fetch:
        import captcha as cap
        user = os.environ.get("JWXT_USER")
        pwd = os.environ.get("JWXT_PWD")
        if not user or not pwd:
            print("缺少凭据：请设置环境变量 JWXT_USER / JWXT_PWD")
            return
        ok, session, reason = cap.login(user, pwd, verbose=False)
        if not ok:
            print("登录失败:", reason)
            return
        # 先取默认学期页面，拿到学期下拉选项后依次轮询
        html0 = fetch_semester(session, "")
        semesters = [v for v, _ in extract_selects(html0).get("xnxq01id", []) if v]
        html = html0
        for sem in semesters:
            html = fetch_semester(session, sem)
            course_rows = parse_grid(html)
            print(f"学期 {sem}: {len(course_rows)} 条课程记录")
            if course_rows:
                with open(HTML_FILE, "w", encoding="utf-8") as f:
                    f.write(html)
                break
        else:
            print("所有学期均无课表数据")
            return
    else:
        if not os.path.isfile(HTML_FILE):
            print("未找到 timetable.html，请先登录抓取（main.py login）或加 --fetch")
            return
        html = open(HTML_FILE, encoding="utf-8").read()

    if args.probe:
        probe(html)
        return

    course_rows = parse_grid(html)
    if not course_rows:
        print("当前页面课表为空（课表尚未生成），可用 --fetch 自动轮询学期。")
        print("可用的学期选项：")
        probe(html)
        return

    text = format_text(course_rows)
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        f.write(text + "\n")
    print(f"解析出 {len(course_rows)} 条课程记录 -> {OUT_FILE}")
    print(text)


if __name__ == "__main__":
    main()
