# -*- coding: utf-8 -*-
"""封面体检：把全站封面拼成一面"对照墙"，同时打印三个坏味道的量化信号。

为什么要有这个工具：
    2026-10-29 换封面翻车一次。松林图标题写着"晨光穿过松林"，看着应景，
    实际是整幅逆光剪影、满屏深色树冠，被作者否掉。事后量了十几张图才看明白：
    **亮度这个单一数值根本不能用**——作者满意的《静坐入门》白莲封面平均亮度
    只有 62，比被否掉的松林 71 还低。真正让人皱眉的是"发灰 + 碎 + 半暗"三样
    同时出现，不是单纯的暗。

    所以这个工具不设"亮度必须大于多少"的死阈值，只做两件事：
      1. 拼出对照墙——封面好不好，要放进整排里看，单看一张会骗人；
      2. 报出三个信号，三中二就亮红灯，提醒回去重挑。

用法：
    python tools/cover_wall.py                    # 全站封面拼墙 + 报指标
    python tools/cover_wall.py 候选.jpg           # 把候选图排最前面，一起看
    python tools/cover_wall.py --no-wall 候选.jpg # 只报指标，不拼图

输出：.workbuddy/previews/封面墙.jpg
"""
import argparse
import glob
import io
import math
import os
import re
import subprocess
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

TOOLS = os.path.dirname(os.path.abspath(__file__))


def find_root(start):
    d = start
    for _ in range(5):
        if os.path.exists(os.path.join(d, "hugo.toml")):
            return d
        d = os.path.dirname(d)
    return start


ROOT = find_root(TOOLS)
POSTS = os.path.join(ROOT, "content", "posts")
IMGS = os.path.join(ROOT, "assets", "images")
OUTDIR = os.path.join(ROOT, ".workbuddy", "previews")
WALL = os.path.join(OUTDIR, "封面墙.jpg")

CELL_W, CELL_H, LABEL_H = 300, 188, 34
COLS = 4
FONT = "C\\:/Windows/Fonts/msyhbd.ttc"

# 三条观察线。都不是"合格线"，是"该回头看一眼"的提醒线。
# 阈值是拿全站 9 张已认可的封面 + 被否的松林图反推出来的，改之前先重跑一遍比对。
DIM_LUM = 90       # 平均亮度低于此：偏暗
GRAY_SAT = 30      # 饱和度低于此：发灰
BUSY_EDGE = 26     # 边缘密度高于此：画面碎（只作参考，有序的重复也会高）


def read(p):
    return io.open(p, encoding="utf-8", errors="replace").read()


def collect():
    """按首页顺序（日期倒序）取每篇的封面。"""
    items = []
    for p in glob.glob(os.path.join(POSTS, "*.md")):
        if os.path.basename(p) == "_index.md":
            continue
        raw = read(p)
        fm = raw
        if raw.startswith("---"):
            i = raw.find("\n---", 3)
            if i > 0:
                fm = raw[3:i]
        cov = re.search(r'cover:\s*\n\s+image:\s*"([^"]+)"', fm)
        if not cov:
            continue
        path = os.path.join(IMGS, os.path.basename(cov.group(1)))
        if not os.path.exists(path):
            continue
        t = re.search(r'^title:\s*"?(.*?)"?\s*$', fm, re.M)
        d = re.search(r"^date:\s*(\S+)", fm, re.M)
        items.append({
            "path": path,
            "title": t.group(1) if t else os.path.basename(path),
            "date": d.group(1) if d else "",
        })
    items.sort(key=lambda x: x["date"], reverse=True)
    return items


def frame(path, w, h, extra=""):
    vf = "scale=%d:%d" % (w, h)
    if extra:
        vf += "," + extra
    r = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", path, "-vf", vf,
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        capture_output=True)
    return r.stdout


def measure(path):
    d = frame(path, 64, 64)
    if not d:
        return None
    n = len(d) // 3
    lum, sat = [], []
    for i in range(n):
        r, g, b = d[3 * i], d[3 * i + 1], d[3 * i + 2]
        lum.append(0.299 * r + 0.587 * g + 0.114 * b)
        mx, mn = max(r, g, b), min(r, g, b)
        sat.append(0 if mx == 0 else (mx - mn) / mx * 100.0)
    mean = sum(lum) / n
    var = sum((x - mean) ** 2 for x in lum) / n
    e = frame(path, 128, 128, "edgedetect=low=0.08:high=0.2")
    en = max(1, len(e) // 3)
    edge = sum((0.299 * e[3 * i] + 0.587 * e[3 * i + 1] + 0.114 * e[3 * i + 2])
               for i in range(en)) / en
    return dict(mean=mean, sd=var ** 0.5,
                dark=100.0 * sum(1 for x in lum if x < 40) / n,
                bright=100.0 * sum(1 for x in lum if x > 150) / n,
                sat=sum(sat) / n, edge=edge)


def safe_label(text, limit=14):
    text = re.sub(r"[\\'\":%\[\]]", "", text)
    text = re.sub(r"\s+", "", text)
    return text[:limit] or "封面"


def build_wall(items, out):
    n = len(items)
    rows = int(math.ceil(n / float(COLS)))
    inputs, chains, tiles = [], [], []

    for idx, it in enumerate(items):
        inputs += ["-i", it["path"]]
        label = os.path.join(OUTDIR, "_lb_%02d.txt" % idx)
        with io.open(label, "w", encoding="utf-8") as f:
            f.write(safe_label(it["title"]))
        chains.append(
            "[%d:v]scale=%d:%d:force_original_aspect_ratio=increase,"
            "crop=%d:%d,pad=%d:%d:0:0:color=0x141414,"
            "drawtext=fontfile='%s':textfile='%s':fontcolor=white:fontsize=17:"
            "x=10:y=%d[v%d]"
            % (idx, CELL_W, CELL_H, CELL_W, CELL_H, CELL_W, CELL_H + LABEL_H,
               FONT, label.replace("\\", "/").replace(":", "\\:"),
               CELL_H + 8, idx))
        col, row = idx % COLS, idx // COLS
        tiles.append("%d_%d" % (col * CELL_W, row * (CELL_H + LABEL_H)))

    # 补空格子，让网格整齐
    blank = rows * COLS - n
    for k in range(blank):
        idx = n + k
        inputs += ["-f", "lavfi", "-i",
                   "color=c=0x141414:s=%dx%d" % (CELL_W, CELL_H + LABEL_H)]
        chains.append("[%d:v]null[v%d]" % (idx, idx))
        col, row = idx % COLS, idx // COLS
        tiles.append("%d_%d" % (col * CELL_W, row * (CELL_H + LABEL_H)))

    # xstack 的输入标签要按顺序排好
    order = []
    for idx in range(rows * COLS):
        order.append("[v%d]" % idx)

    fc = ";".join(chains) + ";" + "".join(order) + \
        "xstack=inputs=%d:layout=%s:fill=0x141414[out]" % (rows * COLS, "|".join(tiles))

    cmd = ["ffmpeg", "-y", "-v", "error"] + inputs + [
        "-filter_complex", fc, "-map", "[out]", "-frames:v", "1",
        "-q:v", "4", out]
    r = subprocess.run(cmd, capture_output=True)
    for f in glob.glob(os.path.join(OUTDIR, "_lb_*.txt")):
        try:
            os.remove(f)
        except OSError:
            pass
    if r.returncode != 0:
        print("拼图失败：" + r.stderr.decode("utf-8", "replace")[:400])
        return False
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cand", nargs="*", help="候选图路径，会排在最前面")
    ap.add_argument("--no-wall", action="store_true", help="只报指标，不拼图")
    args = ap.parse_args()

    os.environ["NO_PROXY"] = "*"
    items = collect()
    cands = [{"path": c, "title": "候选 " + os.path.basename(c), "date": "9999"}
             for c in args.cand if os.path.exists(c)]
    items = cands + items

    if not items:
        print("没找到任何封面。")
        return 1

    print("")
    print("=" * 78)
    print("  封面体检   %d 张" % len(items))
    print("=" * 78)
    print("  %-30s %4s %4s %5s %5s %4s %4s   %s"
          % ("文件", "亮度", "对比", "暗部", "亮部", "饱和", "边缘", "信号"))
    print("  " + "-" * 74)

    flagged = []
    for it in items:
        m = measure(it["path"])
        if not m:
            print("  %-30s 读取失败" % os.path.basename(it["path"]))
            continue
        dim = m["mean"] < DIM_LUM
        gray = m["sat"] < GRAY_SAT
        busy = m["edge"] > BUSY_EDGE
        tags, warn = [], False
        if dim and gray:
            tags.append("灰暗")
            warn = True
        elif dim:
            tags.append("偏暗")
        if busy:
            tags.append("细节多")
        if warn:
            flag = "⚠ " + "、".join(tags)
            flagged.append((os.path.basename(it["path"]), tags))
        elif tags:
            flag = "· " + "、".join(tags)
        else:
            flag = "ok"
        print("  %-30s %4.0f %4.0f %4.0f%% %4.0f%% %4.0f %4.0f   %s"
              % (os.path.basename(it["path"])[:30], m["mean"], m["sd"],
                 m["dark"], m["bright"], m["sat"], m["edge"], flag))

    print("  " + "-" * 74)
    if flagged:
        print("  ⚠ 亮度和饱和度同时偏低，画面会发闷，回去重挑：")
        for name, bad in flagged:
            print("     %s —— %s" % (name, "、".join(bad)))
    else:
        print("  没有一张同时踩到暗和灰，可以进入下一步：自己看图和对照墙。")
    print("  「细节多」只是描述，不是毛病——有秩序的重复（竹林、竹竿）也会高，别当不合格。")

    if not args.no_wall:
        os.makedirs(OUTDIR, exist_ok=True)
        if build_wall(items, WALL):
            print("  对照墙已生成：%s" % WALL)
    print("")
    print("  提醒：数值只用来预警，最终判断只有一条——")
    print("        把图放进这面墙里，它和旁边那几张像不像一个站的。")
    print("")
    return 0


if __name__ == "__main__":
    sys.exit(main())
