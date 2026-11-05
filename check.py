#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置体检脚本（不改动任何学习记录，只做只读探测）

用法：在项目目录下执行
    python check.py
"""

import os
import sys
import warnings

# 屏蔽 urllib3 版本不匹配的无害警告
warnings.filterwarnings("ignore")

from dotenv import load_dotenv

# 在项目目录下找 .env
load_dotenv()

# 导入主程序里的核心类
from main import YuketangHeartbeat


REQUIRED = [
    ("CLASSROOM_ID", "课堂ID（纯数字）"),
    ("SIGN", "URL 里的 sign 参数"),
    ("UNIVERSITY_ID", "学校ID（纯数字）"),
    ("CSRF_TOKEN", "csrftoken 的值"),
    ("SESSION_ID", "sessionid 的值"),
]


def looks_like_placeholder(value: str) -> bool:
    v = (value or "").strip()
    return (not v) or v.startswith("<") or v.endswith(">")


def main() -> int:
    print("=" * 60)
    print("雨课堂配置体检")
    print("=" * 60)

    problems = []
    values = {}

    for key, desc in REQUIRED:
        raw = os.getenv(key, "")
        values[key] = raw
        if looks_like_placeholder(raw):
            problems.append(f"[未填写] {key} ({desc})")
        else:
            masked = raw if len(raw) <= 8 else raw[:4] + "*" * (len(raw) - 8) + raw[-4:]
            print(f"[OK] {key} = {masked}")
            # 纯数字校验
            if key in ("CLASSROOM_ID", "UNIVERSITY_ID") and not raw.strip().isdigit():
                problems.append(f"[格式错] {key} 应该是纯数字，当前是: {raw}")

    if problems:
        print("\n配置有问题，先修好这些：")
        for p in problems:
            print("  -", p)
        print("\n请编辑项目目录下的 .env 文件后重试。")
        return 1

    classroom_id = int(values["CLASSROOM_ID"].strip())
    university_id = int(values["UNIVERSITY_ID"].strip())
    sign = values["SIGN"].strip()
    csrf_token = values["CSRF_TOKEN"].strip()
    session_id = values["SESSION_ID"].strip()

    cookies = {
        "login_type": "WX",
        "csrftoken": csrf_token,
        "sessionid": session_id,
        "django_language": "zh-cn",
        "uv_id": str(university_id),
        "university_id": str(university_id),
        "platform_id": "3",
        "classroomId": str(classroom_id),
        "classroom_id": str(classroom_id),
        "xtbz": "ykt",
        "platform_type": "1",
    }

    print("\n" + "-" * 60)
    print("正在验证登录状态并拉取课程结构...")
    print("-" * 60)

    hb = YuketangHeartbeat(cookies)
    hb.video_params = {
        "uv_id": university_id,
        "university_id": university_id,
        "csrf_token": csrf_token,
    }

    chapters = hb.get_course_chapters(classroom_id, sign)
    if not chapters:
        print("\n[失败] 拿不到课程章节。常见原因：")
        print("  1. SESSION_ID / CSRF_TOKEN 过期 -> 重新登录雨课堂后重新复制")
        print("  2. SIGN 不对或已失效 -> 重新从课程页面 URL 里复制")
        print("  3. CLASSROOM_ID 不属于这个账号 -> 确认课程页 URL")
        return 1

    print("\n[成功] 登录有效，课程章节已获取")

    videos = hb.get_video_leaf_list(classroom_id, sign, debug=False)
    print(f"\n视频数量: {len(videos)}")
    for i, v in enumerate(videos, 1):
        print(f"  {i}. {v['name']}  (章节: {v['chapter_name']})")

    richtexts = hb.get_richtext_leaf_list(classroom_id, sign, debug=False)
    print(f"图文数量: {len(richtexts)}")

    print("\n" + "=" * 60)
    print("体检通过，可以用 `python main.py` 正式运行了。")
    print("提示：.env 里 TEST_MODE=true 时只跑前 TEST_VIDEO_COUNT 个视频，")
    print("      建议先这样验证一遍，没问题再改成 false 跑全部。")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
