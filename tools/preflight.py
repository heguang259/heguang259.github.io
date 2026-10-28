# -*- coding: utf-8 -*-
"""发布前自检：一条命令跑完所有机械核对。

用法：
    python tools/preflight.py            # 只查本地（构建产物 + 源文件）
    python .workbuddy/tools/preflight.py --online   # 再查线上（Cloudflare 域名）

设计原则：所有"能不能上线"的判断都交给程序，不靠记忆。
退出码 0 = 全部通过，1 = 有错误。
"""
import argparse
import glob
import io
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

TOOLS = os.path.dirname(os.path.abspath(__file__))


def find_root(start):
    """从脚本位置向上找 hugo.toml，放在 tools/ 或 .workbuddy/tools/ 都能用。"""
    d = start
    for _ in range(5):
        if os.path.exists(os.path.join(d, "hugo.toml")):
            return d
        d = os.path.dirname(d)
    return start


ROOT = find_root(TOOLS)
PUB = os.path.join(ROOT, "public")
POSTS = os.path.join(ROOT, "content", "posts")
IMGS = os.path.join(ROOT, "assets", "images")

DOMAIN = "xinzhao-biji.pages.dev"
OLD_DOMAIN = "heguang259.github.io"

# 正文里不该出现的公众号导流痕迹
FLOW_KW = ["公众号", "见文末", "回复关键词", "关键词:", "关键词："]

results = []  # (ok: bool|None, 项目, 说明)


def rec(ok, name, detail=""):
    results.append((ok, name, detail))


def read(p):
    return io.open(p, encoding="utf-8", errors="replace").read()


def split_fm(raw):
    if raw.startswith("---"):
        i = raw.find("\n---", 3)
        if i > 0:
            return raw[3:i], raw[i + 4:]
    return "", raw


def strip_md(t):
    t = re.sub(r"^#{1,6}\s*", "", t, flags=re.M)
    t = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", t)
    t = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", t)
    t = t.replace("<!--more-->", "")
    return re.sub(r"\s+", "", t)


def load_posts():
    out = []
    for p in sorted(glob.glob(os.path.join(POSTS, "*.md"))):
        name = os.path.basename(p)
        if name == "_index.md":
            continue
        raw = read(p)
        fm, body = split_fm(raw)
        d = re.search(r"^date:\s*(\S+)", fm, re.M)
        title = re.search(r'^title:\s*"?(.*?)"?\s*$', fm, re.M)
        cov = re.search(r'cover:\s*\n\s+image:\s*"([^"]+)"', fm)
        out.append({
            "file": name,
            "slug": name[:-3],
            "path": p,
            "fm": fm,
            "body": body,
            "date": d.group(1) if d else "",
            "title": title.group(1) if title else name,
            "cover": cov.group(1) if cov else "",
            "words": len(strip_md(body)),
            "more": "<!--more-->" in body,
            "summary": len(re.findall(r"^summary:", fm, re.M)),
        })
    return out


def check_sources(posts):
    """源文件层面：日期、封面路径、重复字段、导流残留、摘要方式。"""
    import datetime

    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
    future, no_cover, dup, flow, no_sum = [], [], [], [], []

    for p in posts:
        if p["date"]:
            try:
                dt = datetime.datetime.fromisoformat(p["date"])
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=now.tzinfo)
                if dt > now:
                    future.append(p["file"])
            except ValueError:
                future.append(p["file"] + "（日期格式无法解析）")
        else:
            future.append(p["file"] + "（没有 date 字段）")

        if p["cover"]:
            if p["cover"].startswith("/"):
                no_cover.append(p["file"] + "（路径带前导斜杠）")
            elif not os.path.exists(os.path.join(IMGS, os.path.basename(p["cover"]))):
                no_cover.append(p["file"] + "（图片不存在：" + p["cover"] + "）")

        if p["summary"] > 1:
            dup.append(p["file"] + "（summary 写了 " + str(p["summary"]) + " 次，YAML 会报错）")

        hits = [k for k in FLOW_KW if k in p["body"]]
        if hits:
            flow.append(p["file"] + "（含 " + "、".join(hits) + "）")

        if not p["more"] and p["summary"] == 0:
            no_sum.append(p["file"] + "（既没有 <!--more--> 也没有 summary，首页会显示全文）")

    rec(not future, "发布日期都在当前时间之前", "；".join(future) if future else "共 %d 篇" % len(posts))
    rec(not no_cover, "封面图路径与文件有效", "；".join(no_cover) if no_cover else "全部正常")
    rec(not dup, "front matter 无重复字段", "；".join(dup) if dup else "无重复")
    rec(not flow, "正文无公众号导流残留", "；".join(flow) if flow else "全部干净")
    rec(not no_sum, "每篇都有摘要控制", "；".join(no_sum) if no_sum else "全部已设")


def check_build(posts):
    """构建产物层面：页面是否生成、首页摘要、域名残留、图片与死链。"""
    if not os.path.isdir(PUB):
        rec(False, "public 目录存在", "没找到构建产物，先跑 hugo")
        return

    missing = [p["slug"] for p in posts
               if not os.path.exists(os.path.join(PUB, "posts", p["slug"], "index.html"))]
    rec(not missing, "每篇文章都生成了页面",
        ("未生成：" + "、".join(missing) + "（多半是日期在未来）") if missing else "共 %d 篇" % len(posts))

    home = os.path.join(PUB, "index.html")
    if os.path.exists(home):
        h = read(home)
        long_sum = []
        for a in re.findall(r"<article class=[^>]*>(.*?)</article>", h, re.S):
            m = re.search(r"entry-content[^>]*>(.*?)</div>", a, re.S)
            t = re.search(r'entry-hint-parent[^>]*>(.*?)</h2>', a, re.S)
            if m:
                txt = re.sub(r"\s+", "", re.sub(r"<[^>]+>", "", m.group(1)))
                if len(txt) > 400:
                    long_sum.append((re.sub(r"<[^>]+>", "", t.group(1)) if t else "?")[:16] + "（%d 字）" % len(txt))
        rec(not long_sum, "首页摘要是摘要不是全文",
            "；".join(long_sum) if long_sum else "全部在 400 字以内")
    else:
        rec(False, "首页 index.html 存在", "缺失")

    # 域名残留 + 图片与链接可达（本地存在性）
    old_hits, num_hits, bad_links, bad_imgs = [], [], [], []
    for f in glob.glob(os.path.join(PUB, "**", "*.html"), recursive=True):
        h = read(f)
        rel = f.replace(PUB, "")
        if OLD_DOMAIN in h:
            old_hits.append(rel + "（%d 处）" % h.count(OLD_DOMAIN))
        n = len(re.findall(r"[0-9a-f]{8}\." + re.escape(DOMAIN), h))
        if n:
            num_hits.append(rel + "（%d 处）" % n)
        for m in re.finditer(r'href="(?:https://[^/"]+)?(/[^"#?]*)"', h):
            u = urllib.parse.unquote(m.group(1))
            if u.startswith(("/images/", "/assets/")):
                continue
            if not os.path.exists(os.path.join(PUB, u.lstrip("/").rstrip("/"))):
                bad_links.append(rel + " → " + u)
        for m in re.finditer(r'src="(?:https://[^/"]+)?(/images/[^"]+)"', h):
            if not os.path.exists(os.path.join(PUB, urllib.parse.unquote(m.group(1)).lstrip("/"))):
                bad_imgs.append(rel + " → " + m.group(1))

    rec(not old_hits, "页面无旧域名残留", "；".join(old_hits[:5]) if old_hits else "0 处")
    rec(not num_hits, "页面无带部署编号的地址", "；".join(num_hits[:5]) if num_hits else "0 处（缓存才有效）")
    rec(not bad_imgs, "图片全部存在", "；".join(bad_imgs[:5]) if bad_imgs else "全部命中")
    rec(not bad_links, "站内链接无死链",
        ("%d 条：" % len(bad_links)) + "；".join(bad_links[:5]) if bad_links else "0 条")


def check_online(posts):
    """线上层面：状态码与关键内容。"""
    ua = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/131.0.0.0"}
    base = "https://" + DOMAIN

    def get(url):
        r = urllib.request.urlopen(urllib.request.Request(url, headers=ua), timeout=30)
        return r.status, r.read().decode("utf-8", "replace")

    bad = []
    for p in posts:
        url = base + "/posts/" + p["slug"] + "/"
        try:
            code, h = get(url)
            if code != 200:
                bad.append(p["slug"] + "（HTTP %d）" % code)
            elif p["title"][:6] not in h:
                bad.append(p["slug"] + "（标题不在页面上）")
        except Exception as e:
            bad.append(p["slug"] + "（%s）" % type(e).__name__)
    rec(not bad, "线上文章页全部可访问", "；".join(bad[:6]) if bad else "%d 篇全部 200" % len(posts))

    pages = ["/", "/archives/", "/categories/", "/tags/"]
    bad2 = []
    for u in pages:
        try:
            code, _ = get(base + u)
            if code != 200:
                bad2.append(u + "（HTTP %d）" % code)
        except Exception as e:
            bad2.append(u + "（%s）" % type(e).__name__)
    rec(not bad2, "线上导航页全部可访问", "；".join(bad2) if bad2 else "/ 归档 分类 标签 全 200")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--online", action="store_true", help="同时检查线上站点")
    args = ap.parse_args()

    os.environ["NO_PROXY"] = "*"
    posts = load_posts()
    check_sources(posts)
    check_build(posts)
    if args.online:
        check_online(posts)

    print("")
    print("=" * 72)
    print("  发布前自检  %d 篇文章  %s" % (len(posts), "（含线上）" if args.online else "（仅本地）"))
    print("=" * 72)
    err = 0
    for ok, name, detail in results:
        mark = "✓" if ok else "✗"
        if not ok:
            err += 1
        print("  %s %-26s %s" % (mark, name, detail))
    print("=" * 72)
    if err == 0:
        print("  结论：全部通过，可以提交推送。")
    else:
        print("  结论：%d 项未通过，先修再推。" % err)
    print("")
    return 0 if err == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
