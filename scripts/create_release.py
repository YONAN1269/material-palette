"""在 GitHub 上创建 Release 并挂上 vsix，得到一个可直接下载的安装链接。

用法：python scripts/create_release.py
读取 _gh_token.txt，版本号从 package.json 取。
"""
import json
import os
import sys
import urllib.error
import urllib.request

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API = "https://api.github.com"
UPLOAD = "https://uploads.github.com"


def token():
    p = os.path.join(BASE, "_gh_token.txt")
    if os.path.exists(p):
        t = open(p, encoding="utf-8").read().strip()
        if t:
            return t
    sys.exit("缺少 token：_gh_token.txt")


TOKEN = token()


def call(method, url, payload=None, raw_body=None, content_type=None):
    data = raw_body if raw_body is not None else (
        json.dumps(payload).encode() if payload is not None else None)
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", "Bearer " + TOKEN)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "material-palette-release")
    if data is not None:
        req.add_header("Content-Type", content_type or "application/json")
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, {"error": e.read().decode("utf-8", "replace")[:400]}


pkg = json.load(open(os.path.join(BASE, "package.json"), encoding="utf-8"))
ver = pkg["version"]
owner = "YONAN1269"
repo = "material-palette"
tag = "v" + ver
vsix = os.path.join(BASE, "material-palette-%s.vsix" % ver)
if not os.path.exists(vsix):
    sys.exit("找不到 %s，先跑 rebuild.bat" % os.path.basename(vsix))

body = """Material 风格 VS Code 主题合集，**12 套配色**。

界面一体化取向：侧边栏、活动栏、状态栏、标签栏与编辑区**同一底色、零色差**，
区域之间唯一的区分是 `#00000030` 的压暗阴影 —— 整个窗口像一张连续的纸。

## 安装

1. 下载下面的 `material-palette-%s.vsix`
2. VS Code 里按 `Ctrl+Shift+P` → `Extensions: Install from VSIX...` → 选这个文件
3. `Ctrl+K Ctrl+T` 选主题（列表里是 `Material Palette · Nord` 这种名字）

## 12 套配色

| 深色 | | 浅色 / 高对比 |
|---|---|---|
| Default `#263238` | Ocean `#0F111A` | Lighter `#FAFAFA` |
| Darker `#212121` | Palenight `#292D3E` | High Contrast `#1A2327` |
| Deep Forest `#0D1F17` | Nord `#2E3440` | 4 套 HC 变体 |

## 说明

- 350+ 个 workbench 色槽，82 条 token 规则，开启 semanticHighlighting
- 正文对比度 5.17:1 至 21:1，全部达到 WCAG AA，高对比变体达到 AAA 以上
- 所有主题由 `scripts/generate_themes.py` 生成，语义配色在 12 套之间完全统一

喜欢的话可以扫 README 里的赞赏码，完全自愿。
""" % ver

print("[1/3] 创建 release %s ..." % tag)
st, r = call("POST", "%s/repos/%s/%s/releases" % (API, owner, repo), {
    "tag_name": tag,
    "name": "Material Palette %s — 12 套配色" % ver,
    "body": body,
    "draft": False,
    "prerelease": False,
})
if st == 422:
    print("  · release 已存在，改为查询")
    st2, r = call("GET", "%s/repos/%s/%s/releases/tags/%s" % (API, owner, repo, tag))
    st, r = st2, r
if st not in (200, 201):
    print("  ✗ HTTP %s %s" % (st, str(r)[:400]))
    sys.exit(1)
print("  ✓ %s" % r["html_url"])
rel_id = r["id"]

print("[2/3] 检查是否已挂过 vsix ...")
assets = [a["name"] for a in r.get("assets", [])]
name = os.path.basename(vsix)
if name in assets:
    print("  · 已存在 %s，跳过上传" % name)
else:
    print("  · 上传 %s (%.1f KB) ..." % (name, os.path.getsize(vsix) / 1024))
    st, a = call("POST",
                 "%s/repos/%s/%s/releases/%d/assets?name=%s"
                 % (UPLOAD, owner, repo, rel_id, name),
                 raw_body=open(vsix, "rb").read(),
                 content_type="application/octet-stream")
    if st not in (200, 201):
        print("  ✗ HTTP %s %s" % (st, str(a)[:400]))
        sys.exit(1)
    print("  ✓ %s (%d bytes)" % (a["name"], a["size"]))

print("[3/3] 下载地址 ...")
dl = "https://github.com/%s/%s/releases/latest/download/%s" % (owner, repo, name)
req = urllib.request.Request(dl, method="HEAD")
req.add_header("User-Agent", "Mozilla/5.0")
try:
    with urllib.request.urlopen(req, timeout=40) as resp:
        print("  ✓ %s" % dl)
        print("    HTTP %s  %s KB" % (resp.status,
              round(int(resp.headers.get("Content-Length", 0)) / 1024, 1)))
except urllib.error.HTTPError as e:
    print("  · %s  HTTP %s（刚发布时可能有缓存延迟）" % (dl, e.code))
