#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 vsix 里的 readme.md 换成"绝对 https 图片地址"版本。

为什么必须这样做：
    VS Code 的扩展详情页、以及扩展市场页面，都**只渲染绝对 https 图片地址**。
    README 里写 assets/wechat-pay.jpg 这种相对路径，一定裂图。

    vsce 打包时会尝试把相对路径改写成 {repository}/raw/HEAD/...，
    但那个地址要求仓库真实存在。仓库还没建的时候，改出来就是死链。

做法：
    读取 publish.ini 里的 IMAGES（图片目录的 https 地址），
    把源 README.md 里的 assets/xxx 全部替换成 IMAGES/xxx，
    然后覆盖写进 vsix 的 extension/readme.md。

    IMAGES 没填时：原样写入相对路径，并明确警告会裂图。
"""
import io
import os
import re
import shutil
import sys
import zipfile

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INI = os.path.join(BASE, "publish.ini")


def read_images_base():
    if not os.path.exists(INI):
        return ""
    for raw in open(INI, encoding="utf-8-sig"):
        line = raw.strip()
        if line.upper().startswith("IMAGES"):
            if "=" not in line:
                continue
            val = line.split("=", 1)[1].split(" #")[0].split(";")[0].strip()
            return val.rstrip("/")
    return ""


def rewrite(markdown, base):
    """assets/xxx -> <base>/xxx，同时兼容 HTML img 与 Markdown 图片语法。"""
    count = 0
    if not base:
        return markdown, 0

    def to_url(src):
        """相对路径转绝对地址。

        IMAGES 既可以填「assets 目录地址」(.../main/assets)，
        也可以填「仓库根地址」(.../main)，这里自动判断，避免出现 assets/assets 双写。
        """
        rel = src.lstrip("./")
        if rel.startswith("assets/"):
            folder = "assets" if not base.endswith("/assets") else ""
            rel = rel[len("assets/"):]
            return (base + "/" + folder + "/" + rel) if folder else (base + "/" + rel)
        return base + "/" + rel

    def html_sub(m):
        nonlocal count
        src = m.group(2)
        if re.match(r"^([a-z]+:)?//", src, re.I) or src.startswith("data:"):
            return m.group(0)
        count += 1
        return '%s="%s"' % (m.group(1), to_url(src))

    markdown = re.sub(r'(src)="([^"]+)"', html_sub, markdown)

    def md_sub(m):
        nonlocal count
        src = m.group(2)
        if re.match(r"^([a-z]+:)?//", src, re.I) or src.startswith("data:"):
            return m.group(0)
        count += 1
        return "%s(%s)" % (m.group(1), to_url(src))

    markdown = re.sub(r"(!\[[^\]]*\])\(([^)]+)\)", md_sub, markdown)
    return markdown, count


def main(vsix):
    if not os.path.exists(vsix):
        print("vsix not found:", vsix)
        return 1

    src = os.path.join(BASE, "README.md")
    markdown = io.open(src, encoding="utf-8").read()

    base = read_images_base()
    markdown, count = rewrite(markdown, base)

    if base:
        print("readme 图片地址已改为绝对链接（%d 处）: %s/..." % (count, base))
    else:
        print("  !! publish.ini 的 IMAGES 是空的：readme 里仍是相对路径，")
        print("     扩展详情页和扩展市场里的赞赏码会裂图。填好 IMAGES 再重新打包即可。")

    tmp = vsix + ".tmp"
    found = False
    with zipfile.ZipFile(vsix) as zin, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename.lower() == "extension/readme.md":
                data = markdown.encode("utf-8")
                found = True
            zout.writestr(item, data)
    shutil.move(tmp, vsix)

    if not found:
        print("  !! vsix 里没有 extension/readme.md，检查 .vscodeignore 是否把 README 排除了")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "material-palette-1.3.1.vsix"))
