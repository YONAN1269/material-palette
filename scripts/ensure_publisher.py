"""用 Azure DevOps PAT 直接创建 Marketplace 发布者（绕开会转圈的网页）。

用法：
    1. 把 PAT 写入 _ado_token.txt（一行，不要空格）
    2. python scripts/ensure_publisher.py

背景：marketplace 的「Create publisher」网页在部分浏览器（Brave 开了 Shields、
或禁用了第三方 cookie）里会一直转圈，实际请求没回来。这里直接调
POST https://marketplace.visualstudio.com/_apis/gallery/publishers
"""
import base64
import json
import os
import sys
import urllib.error
import urllib.request

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GALLERY = "https://marketplace.visualstudio.com"
API_VER = "3.0-preview.1"


def read(name):
    p = os.path.join(BASE, name)
    if os.path.exists(p):
        v = open(p, encoding="utf-8").read().strip()
        if v:
            return v
    return ""


def ini(key, default=""):
    p = os.path.join(BASE, "publish.ini")
    for line in open(p, encoding="utf-8"):
        if line.split("=")[0].strip() == key:
            return line.split("=", 1)[1].strip() or default
    return default


PUBLISHER = ini("PUBLISHER")
DISPLAY = "Yonan"          # 市场页上显示的名字，可随意改
DESC = "Material 风格 VS Code 主题：12 套配色，界面一体化"

TOKEN = read("_ado_token.txt") or os.environ.get("ADO_TOKEN", "").strip()
if not TOKEN:
    sys.exit("缺少 PAT：请把 Azure DevOps token 写入 _ado_token.txt（一行）")
if not PUBLISHER:
    sys.exit("publish.ini 里的 PUBLISHER 为空")


def call(method, path, payload=None):
    url = GALLERY + path
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    # gallery 接口用 Basic，用户名留空
    req.add_header("Authorization",
                   "Basic " + base64.b64encode((":" + TOKEN).encode()).decode())
    req.add_header("Accept", "application/json;api-version=" + API_VER)
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "material-palette-publisher")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


print("发布者 ID : %s" % PUBLISHER)
print("显示名称   : %s" % DISPLAY)
print()

body = {
    "publisherName": PUBLISHER,
    "displayName": DISPLAY,
    "description": DESC,
    "links": [],
    "flags": 0,
}
if DISPLAY.lower() == PUBLISHER.lower():
    body["flags"] = 0

print("[1/2] 创建发布者 ...")
st, txt = call("POST", "/_apis/gallery/publishers", body)

if st in (200, 201):
    print("  ✓ 创建成功 (HTTP %d)" % st)
elif st == 409:
    print("  ✓ 已经存在，无需重复创建 (HTTP 409)")
elif st == 401:
    print("  ✗ 401：PAT 无效或已过期")
    print("    " + txt[:300])
    sys.exit(1)
elif st == 403:
    print("  ✗ 403：PAT 缺少 Marketplace → Manage 权限，或 Organization 没选 All accessible organizations")
    print("    " + txt[:300])
    sys.exit(1)
elif st == 302:
    print("  ✗ 被重定向到登录页：PAT 没被接受")
    print("    " + txt[:300])
    sys.exit(1)
else:
    print("  ? 返回 HTTP %d" % st)
    print("    " + txt[:500])
    print("  如果这里提示已存在/名称被占用，说明发布者已经建好了，可以直接进入发布步骤。")

print()
print("[2/2] 校验管理页可访问 ...")
req = urllib.request.Request(GALLERY + "/manage/publishers/" + PUBLISHER,
                             headers={"User-Agent": "Mozilla/5.0"})
try:
    with urllib.request.urlopen(req, timeout=30) as r:
        print("  ✓ https://marketplace.visualstudio.com/manage/publishers/%s (HTTP %d)"
              % (PUBLISHER, r.status))
except urllib.error.HTTPError as e:
    print("  HTTP %d（302 属正常，表示需要登录）" % e.code)

print()
print("下一步：npx @vscode/vsce publish --packagePath material-palette-*.vsix --pat <PAT>")
