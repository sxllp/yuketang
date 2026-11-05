#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
定点补跑：只处理完成率未满 100% 的视频。

主程序判断 rate>=0.9 即视为"已完成"，所以卡在 90~99% 的视频会被一直跳过，
本脚本绕过该判断，从上次停止位置续播到达 100%。

用法：
    python fixup.py 3.3 6.1
（参数为视频名称前缀，可给多个）
"""
import os
import sys
import warnings

warnings.filterwarnings("ignore")
from dotenv import load_dotenv

load_dotenv()
from main import YuketangHeartbeat

cid = int(os.getenv("CLASSROOM_ID", "0"))
uv = int(os.getenv("UNIVERSITY_ID", "0"))
sign = os.getenv("SIGN", "").strip()
csrf = os.getenv("CSRF_TOKEN", "").strip()
sid = os.getenv("SESSION_ID", "").strip()
speed = float(os.getenv("VIDEO_SPEED", "1.5"))
interval = int(os.getenv("HEARTBEAT_INTERVAL", "5"))

cookies = {
    "login_type": "WX", "csrftoken": csrf, "sessionid": sid,
    "django_language": "zh-cn", "uv_id": str(uv), "university_id": str(uv),
    "platform_id": "3", "classroomId": str(cid), "classroom_id": str(cid),
    "xtbz": "ykt", "platform_type": "1",
}

targets = sys.argv[1:]
if not targets:
    print("请给出要补的视频名称前缀，例如: fixup.py 3.3 6.1")
    sys.exit(2)

hb = YuketangHeartbeat(cookies)
hb.video_params = {"uv_id": uv, "university_id": uv, "csrf_token": csrf}

videos = hb.get_video_leaf_list(cid, sign)
picked = [v for v in videos if any(v["name"].startswith(t) or t in v["name"] for t in targets)]
if not picked:
    print("没匹配到视频:", targets)
    sys.exit(2)

print(f"命中 {len(picked)} 个：{[v['name'] for v in picked]}\n")

ok = 0
for v in picked:
    print("=" * 60)
    print(f"处理: {v['name']} (ID: {v['id']})")
    worker = hb.create_worker_instance()
    if not worker.auto_configure_from_ids(cid, v["id"], sign):
        print("  配置失败，跳过")
        continue

    info = worker.get_current_progress_info()
    if info:
        print(f"  当前进度: {info['rate']:.2%}, 位置 {info['last_point']:.1f}s / {info['duration']:.1f}s")
        if info["rate"] >= 0.999:
            print("  已满 100%，无需处理")
            ok += 1
            continue
        start = max(0, info["last_point"] - 10)
    else:
        print("  无进度记录，从头开始")
        start = 0

    if worker.simulate_video_watching(speed=speed, interval=interval, start_position=start):
        after = worker.get_current_progress_info()
        print(f"  ✅ 完成，服务器进度: {after['rate']:.2%}" if after else "  ✅ 完成")
        ok += 1
    else:
        print("  ❌ 失败")

print("=" * 60)
print(f"补跑结束：成功 {ok}/{len(picked)}")
