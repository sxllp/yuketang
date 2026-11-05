#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
进度核验脚本：逐个向服务器查询全部视频的真实完成率（只读，不产生学习记录）

用法：在项目目录下执行
    python verify.py
"""
import io
import os
import sys
import warnings
from contextlib import redirect_stdout

warnings.filterwarnings("ignore")

from dotenv import load_dotenv

load_dotenv()
from main import YuketangHeartbeat

cid = int(os.getenv("CLASSROOM_ID", "0"))
uv = int(os.getenv("UNIVERSITY_ID", "0"))
sign = os.getenv("SIGN", "").strip()
csrf = os.getenv("CSRF_TOKEN", "").strip()
sid = os.getenv("SESSION_ID", "").strip()

cookies = {
    "login_type": "WX", "csrftoken": csrf, "sessionid": sid,
    "django_language": "zh-cn", "uv_id": str(uv), "university_id": str(uv),
    "platform_id": "3", "classroomId": str(cid), "classroom_id": str(cid),
    "xtbz": "ykt", "platform_type": "1",
}

hb = YuketangHeartbeat(cookies)
hb.video_params = {"uv_id": uv, "university_id": uv, "csrf_token": csrf}

with redirect_stdout(io.StringIO()):
    videos = hb.get_video_leaf_list(cid, sign)

rows = []
for v in videos:
    rate = None
    try:
        with redirect_stdout(io.StringIO()):
            hb.auto_configure_from_ids(cid, v["id"], sign)
        info = hb.get_current_progress_info()
        if info:
            rate = info["rate"]
    except Exception as e:
        rows.append((v["name"], None, str(e)[:60]))
        continue
    rows.append((v["name"], rate, ""))

done = [r for r in rows if r[1] is not None and r[1] >= 0.999]
partial = [r for r in rows if r[1] is not None and r[1] < 0.999]
unknown = [r for r in rows if r[1] is None]

print("=" * 64)
print(f"共 {len(rows)} 个视频：满进度 {len(done)}，未满 {len(partial)}，取不到 {len(unknown)}")
print("=" * 64)

if partial:
    print("\n[未满 100%]")
    for name, rate, _ in sorted(partial, key=lambda x: x[1]):
        print(f"  {rate * 100:6.2f}%  {name}")

if unknown:
    print("\n[取不到进度]")
    for name, _, err in unknown:
        print(f"  ???     {name}  {err}")

if done:
    print(f"\n[已满] {len(done)} 个：")
    print("  " + "、".join(n for n, _, _ in done))

sys.exit(0 if not partial and not unknown else 1)
