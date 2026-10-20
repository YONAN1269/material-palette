"""把 assets 与项目文件上传到你自己的 GitHub 仓库，并回写 publish.ini。

用法（token 只放在本地临时文件里，不写进任何提交）：
    1. 新建 _gh_token.txt，里面只放一行 token（ghp_ 开头）
    2. python scripts/upload_assets.py

流程：
    读 token -> 查登录名 -> 建仓库（已存在则跳过）-> 逐个上传文件
    -> 校验 raw 地址可访问 -> 回写 publish.ini 的 IMAGES / REPO / PUBLISHER
"""
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = "material-palette"
API = "https://api.github.com"


def token():
    p = os.path.join(BASE, "_gh_token.txt")
    if os.path.exists(p):
        t = open(p, encoding="utf-8").read().strip()
        if t:
            return t
    t = os.environ.get("GITHUB_TOKEN", "").strip()
    if t:
        return t
    sys.exit("没有找到 token：请把 token 写入 _gh_token.txt（一行，不要有空格）")


TOKEN = token()


def call(method, url, payload=None, raw=False):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", "Bearer " + TOKEN)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    req.add_header("User-Agent", "material-palette-uploader")
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            body = r.read()
            return r.status, (body if raw else json.loads(body or b"{}"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        return e.code, {"error": body}


def expect(step, status, ok=(200, 201, 204), body=None):
    if status not in ok:
        print("  ✗ %s 失败 (HTTP %s)" % (step, status))
        if body:
            print("    " + str(body)[:400])
        sys.exit(1)
    print("  ✓ %s" % step)


# ---------------------------------------------------------------- 1. 身份
print("[1/5] 校验 token ...")
st, me = call("GET", API + "/user")
expect("token 有效", st, body=me)
owner = me["login"]
print("      登录名：%s" % owner)

# ---------------------------------------------------------------- 2. 仓库
print("[2/5] 准备仓库 %s/%s ..." % (owner, REPO))
st, r = call("GET", "%s/repos/%s/%s" % (API, owner, REPO))
if st == 200:
    print("  ✓ 仓库已存在，直接复用")
else:
    st, r = call("POST", API + "/user/repos", {
        "name": REPO,
        "description": "Material 风格 VSCode 主题合集：12 套配色，界面一体化（所有区域同底色、零色差）",
        "private": False,
        "has_issues": True,
        "has_wiki": False,
    })
    if st == 422:
        print("  ✓ 仓库已存在（422），继续")
    else:
        expect("创建仓库", st, body=r)

st, info = call("GET", "%s/repos/%s/%s" % (API, owner, REPO))
branch = info.get("default_branch", "main")
print("      默认分支：%s" % branch)

# ---------------------------------------------------------------- 3. 上传
TEXT_EXT = {".md", ".json", ".py", ".txt", ".ini", ".bat", ".html",
            ".png_skip", ".gitignore", ""}
SKIP = {"material-palette-1.3.1.vsix", "_gh_token.txt"}


def walk_files():
    out = []
    for root, dirs, files in os.walk(BASE):
        dirs[:] = [d for d in dirs if d not in
                   (".git", "__pycache__", ".workbuddy", ".vscode")]
        for f in files:
            if f in SKIP or f.endswith(".vsix") or f.startswith("_"):
                continue
            full = os.path.join(root, f)
            rel = os.path.relpath(full, BASE).replace("\\", "/")
            if rel.split("/")[0] in ("assets", "themes", "scripts") or rel in (
                "README.md", "CHANGELOG.md", "LICENSE", "package.json",
                "icon.png", "tune.ini",
            ):
                out.append((rel, full))
    return sorted(out)


print("[3/5] 上传文件 ...")
files = walk_files()
uploaded = 0
for rel, full in files:
    blob = open(full, "rb").read()
    sha = None
    st, cur = call("GET", "%s/repos/%s/%s/contents/%s?ref=%s"
                   % (API, owner, REPO, rel, branch))
    if st == 200 and isinstance(cur, dict):
        sha = cur.get("sha")
    payload = {
        "message": "update " + rel if sha else "add " + rel,
        "content": base64.b64encode(blob).decode(),
        "branch": branch,
    }
    if sha:
        payload["sha"] = sha
    st, r = call("PUT", "%s/repos/%s/%s/contents/%s"
                 % (API, owner, REPO, rel), payload)
    if st in (200, 201):
        uploaded += 1
        print("  ✓ %-42s %6.1f KB" % (rel, len(blob) / 1024))
    else:
        print("  ✗ %-42s HTTP %s" % (rel, st))
        print("    " + str(r)[:300])
        sys.exit(1)
    time.sleep(0.2)
print("      共上传 %d 个文件" % uploaded)

# ---------------------------------------------------------------- 4. 验证
print("[4/5] 校验图片公网可访问 ...")
raw_base = "https://raw.githubusercontent.com/%s/%s/%s" % (owner, REPO, branch)
cdn_base = "https://cdn.jsdelivr.net/gh/%s/%s@%s" % (owner, REPO, branch)
ok_img = True
for rel in ("assets/wechat-pay.jpg", "assets/overview.png"):
    url = raw_base + "/" + rel
    try:
        req = urllib.request.Request(url, method="HEAD")
        req.add_header("User-Agent", "Mozilla/5.0")
        with urllib.request.urlopen(req, timeout=30) as resp:
            print("  ✓ %s  HTTP %s  %s KB" % (rel, resp.status,
                  round(int(resp.headers.get("Content-Length", 0)) / 1024, 1)))
    except Exception as e:
        ok_img = False
        print("  ✗ %s  %s" % (rel, e))
if not ok_img:
    print("      raw 地址不可访问，改用 jsDelivr：%s" % cdn_base)

# ---------------------------------------------------------------- 5. 回写
print("[5/5] 回写 publish.ini ...")
p = os.path.join(BASE, "publish.ini")
s = open(p, encoding="utf-8").read()
images = (raw_base if ok_img else cdn_base) + "/assets"
lines = s.splitlines()
for i, line in enumerate(lines):
    key = line.split("=")[0].strip()
    if key == "IMAGES":
        lines[i] = "IMAGES = " + images
    elif key == "REPO":
        lines[i] = "REPO = https://github.com/%s/%s" % (owner, REPO)
    elif key == "PUBLISHER":
        lines[i] = "PUBLISHER = " + owner
open(p, "w", encoding="utf-8", newline="\n").write("\n".join(lines) + "\n")
print("      IMAGES    = %s" % images)
print("      REPO      = https://github.com/%s/%s" % (owner, REPO))
print("      PUBLISHER = %s" % owner)
print()
print("完成。仓库地址：https://github.com/%s/%s" % (owner, REPO))
