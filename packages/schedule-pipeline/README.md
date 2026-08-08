# schedule-pipeline — 课表全链路

从教务系统登录抓取课表 → 验证码识别 → HTML 解析 → 数据库存储 → 前端展示的完整链路。

## 全链路流程

```
1. 登录教务系统（验证码识别）
   captcha_solver/main.py login --user xx --pwd xx
   ├─ captcha.py        教务系统会话/验证码下载
   ├─ preprocess.py     验证码图像预处理
   ├─ segment.py        字符切分
   ├─ recognize.py      字符识别（模板匹配 → CNN/OCR 兜底）
   └─ models/           模板库 + CNN 模型(cnn.pth)

2. 课表解析
   parse_timetable.py   解析抓到的课表 HTML → 文字版 timetable_parsed.txt

3. 数据入库
   course_app/seed.py   把解析结果写入 courses.db

4. 展示服务
   course_app/main.py   FastAPI 服务 + 前端页面
```

## 目录结构

```
schedule-pipeline/
├── README.md
├── captcha_solver/            # 抓取 + 识别 + 解析（CLI）
│   ├── main.py                # 入口：solve/collect/synthgen/train/login
│   ├── captcha.py             # 教务系统会话、验证码下载
│   ├── preprocess.py          # 图像预处理
│   ├── segment.py             # 字符切分
│   ├── recognize.py           # 识别器
│   ├── train.py               # CNN 训练（可选兜底）
│   ├── build_templates.py     # 模板库构建
│   ├── parse_timetable.py     # 课表 HTML 解析
│   ├── requirements.txt
│   ├── timetable.html         # 抓取的课表原始页（示例）
│   ├── timetable_parsed.txt   # 解析后的文字课表（示例）
│   └── models/                # 模板库 + CNN 模型
└── course_app/                # 课表展示（FastAPI）
    ├── main.py                # FastAPI：/course, /api/course, /api/meta
    ├── database.py            # 数据库读写
    ├── seed.py                # 种子数据写入
    ├── _verify_api.py         # API 自检脚本
    ├── courses.db             # SQLite 课表库（示例数据）
    ├── templates/course.html  # 课表页面
    └── static/                # 前端 css/js
```

> 注：captcha_solver 的 `samples/`（训练切图样本，1.5MB）与 `__pycache__` 未打包，
> 如需要从原目录 `d:\project\server\captcha_solver\samples` 复制。

## 使用

### 环境
```bash
# Python 3.10+
pip install -r captcha_solver/requirements.txt
```

### 抓取课表
```bash
# 完整登录并抓取课表（会弹验证码识别流程）
python captcha_solver/main.py login --user 学号 --pwd 密码

# 解析已抓取的课表 HTML → timetable_parsed.txt
python captcha_solver/parse_timetable.py
```

### 启动展示服务
```bash
cd course_app
pip install fastapi uvicorn
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
# 浏览器访问 http://localhost:8000/course
# API:  GET /api/course         全部课程 JSON
#        GET /api/course?week=N  第 N 周课程
#        GET /api/meta           学期/周历元信息
```

## 对接 snhgn.me 网站

课表数据可通过 `/api/course` 供 Vue 网站调用：
- 本地开发：`vite.config.ts` 已预留 `/api` 代理到 `localhost:8000`
- 生产：Caddyfile 增加反向代理 `/dashboard/schedule` → 课表服务
