#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""北林教务系统工具箱命令行测试脚本。

可在服务器或本地直接运行：
    python run_toolbox.py --plan
    python run_toolbox.py --classrooms
    python run_toolbox.py --grades
    python run_toolbox.py --exams
    python run_toolbox.py --all
"""
import argparse
import json
import os
import sys

# 自动处理模块路径
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from app.schedule import captcha, toolbox


def load_credentials_from_env():
    """尝试从常见路径读取已有凭据配置。"""
    user = os.environ.get("BJFU_USERNAME", "")
    pwd = os.environ.get("BJFU_PASSWORD", "")
    if user and pwd:
        return user, pwd

    env_paths = [
        "/opt/bjfu-login/config/config.env",
        os.path.join(parent_dir, ".env"),
    ]
    for ep in env_paths:
        if os.path.exists(ep):
            try:
                with open(ep, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("BJFU_USERNAME="):
                            user = line.split("=", 1)[1].strip().strip('"').strip("'")
                        elif line.startswith("BJFU_PASSWORD="):
                            pwd = line.split("=", 1)[1].strip().strip('"').strip("'")
                if user and pwd:
                    return user, pwd
            except Exception:
                pass
    return "260101208", "Qq513512686@"


def main():
    parser = argparse.ArgumentParser(description="BJFU Educational Administration Toolbox CLI")
    parser.add_argument("-u", "--user", default="", help="学号")
    parser.add_argument("-p", "--password", default="", help="教务密码")
    parser.add_argument("--grades", action="store_true", help="查询各科成绩与GPA")
    parser.add_argument("--exams", action="store_true", help="查询考试日程安排")
    parser.add_argument("--classrooms", action="store_true", help="查询空闲自习教室")
    parser.add_argument("--plan", action="store_true", help="查询四年培养方案要求")
    parser.add_argument("--level-exams", action="store_true", help="查询四六级等社会等级考试")
    parser.add_argument("--all", action="store_true", help="执行全部模块测试")
    args = parser.parse_args()

    user = args.user
    pwd = args.password
    if not user or not pwd:
        default_user, default_pwd = load_credentials_from_env()
        user = user or default_user
        pwd = pwd or default_pwd

    if not any([args.grades, args.exams, args.classrooms, args.plan, args.level_exams, args.all]):
        args.all = True

    print(f"[*] 正在为学号 {user} 登录北林强智教务系统...")
    success, sess, reason = captcha.login(user, pwd, verbose=False)
    if not success:
        print(f"[-] 登录失败: {reason}")
        sys.exit(1)

    print("[+] 登录成功！会话已建立。\n")

    if args.grades or args.all:
        print("=" * 30 + " 成绩查询 (Grades) " + "=" * 30)
        grades = toolbox.get_grades(sess)
        print(f"总计修读科目: {grades['total_courses']} 门")
        print(f"总计学分: {grades['total_credits']}")
        print(f"平均学分绩点 (GPA): {grades['avg_gpa']}")
        print(f"加权平均分: {grades['avg_score']}")
        if grades["courses"]:
            print("最近课程成绩样例:")
            for c in grades["courses"][:5]:
                print(f"  - [{c['term']}] {c['name']} (编号: {c['code']}): 成绩 {c['score']} / {c['credit']}学分 ({c['attribute']})")
        print()

    if args.exams or args.all:
        print("=" * 30 + " 考试日程 (Exams) " + "=" * 30)
        exams = toolbox.get_exams(sess)
        print(f"安排考试场次: {len(exams)}")
        for e in exams:
            print(f"  - {e['name']}: {e['time']} @ {e['room']} (座位: {e['seat']}, 场次: {e['batch']})")
        print()

    if args.classrooms or args.all:
        print("=" * 30 + " 空闲自习教室 (Classrooms) " + "=" * 30)
        # 默认查本周二 1-2 节一教
        rooms = toolbox.get_free_classrooms(sess, building="001", week=3, day=2, start_period=1, end_period=2)
        print(f"一教(001) 第3周周二 1-2节 空闲教室数: {len(rooms)}")
        print("可用教室清单样例:")
        for r in rooms[:6]:
            print(f"  - 教室: {r['name']} | 容量: {r['capacity']}")
        print()

    if args.plan or args.all:
        print("=" * 30 + " 培养方案 (Training Plan) " + "=" * 30)
        plan = toolbox.get_training_plan(sess)
        print(f"培养方案总计要求修读科目: {len(plan)} 门")
        print("前 5 门必修课程样例:")
        for p in plan[:5]:
            print(f"  - [{p['term']}] {p['name']} ({p['code']}): {p['credit']}学分 / {p['hours']}学时 [{p['attribute']}] - {p['dept']}")
        print()

    if args.level_exams or args.all:
        print("=" * 30 + " 等级考试 (Level Exams) " + "=" * 30)
        levels = toolbox.get_level_exams(sess)
        print(f"等级考试记录数: {len(levels)}")
        for lv in levels:
            print(f"  - {lv['name']} ({lv['level']}): 考试时间 {lv['time']}, 成绩 {lv['score']}")
        print()

    sess.close()
    print("[*] 全部功能测试完成！")


if __name__ == "__main__":
    main()
