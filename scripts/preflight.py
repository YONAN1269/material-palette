#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""发布前体检：任何一项不通过，都不该按发布键。

检查的是"上市场之后会不会当场被用户看出问题"的东西：
    - 图片地址有没有配（不然详情页赞赏码裂图）
    - publisher 是不是还是占位的 local（这样根本发不出去）
    - 仓库地址是不是占位（市场页上会挂一个死链接）
    - 名字/描述长度有没有超市场限制（超了会被截断）
    - 图标、许可证、12 个主题文件是否齐全
"""
import io
import json
import os
import struct
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
problems = []
warnings = []
ok = []


def read_ini(path):
    data = {}
    if not os.path.exists(path):
        return data
    for raw in open(path, encoding="utf-8-sig"):
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith(";") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        data[key.strip().upper()] = val.split(" #")[0].split(";")[0].strip()
    return data


def png_size(path):
    with open(path, "rb") as f:
        head = f.read(24)
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    return struct.unpack(">II", head[16:24])


def main():
    cfg = read_ini(os.path.join(BASE, "publish.ini"))
    pkg = json.load(io.open(os.path.join(BASE, "package.json"), encoding="utf-8"))

    images = cfg.get("IMAGES", "")
    if images:
        if not images.startswith("https://"):
            problems.append("publish.ini 的 IMAGES 必须以 https:// 开头（市场只认 https）")
        else:
            for name in ("wechat-pay.jpg", "overview.png"):
                if not os.path.exists(os.path.join(BASE, "assets", name)):
                    problems.append("assets/%s 不存在，但 README 引用了它" % name)
            ok.append("图片地址已配置：%s" % images)
    else:
        problems.append("publish.ini 的 IMAGES 是空的 —— 详情页和市场页的赞赏码会裂图")

    publisher = pkg.get("publisher", "")
    if not publisher or publisher == "local":
        problems.append("publisher 还是占位的 local，市场不收；在 publish.ini 填 PUBLISHER")
    else:
        ok.append("publisher = %s" % publisher)

    repo = (pkg.get("repository") or {}).get("url", "")
    if "your-name" in repo or not repo:
        warnings.append("repository 还是占位地址，市场页的仓库链接会是死链（不拦发布，但建议填）")
    else:
        ok.append("repository = %s" % repo)

    display = pkg.get("displayName", "")
    if len(display) > 45:
        warnings.append("displayName 超过 45 字符，市场列表里会被截断（当前 %d）" % len(display))
    else:
        ok.append("displayName 长度 %d / 45" % len(display))

    desc = pkg.get("description", "")
    if len(desc) > 120:
        warnings.append("description 超过 120 字符，搜索里会被截断（当前 %d）" % len(desc))
    else:
        ok.append("description 长度 %d / 120" % len(desc))

    if pkg.get("license") != "MIT":
        warnings.append("license 建议写 MIT（当前 %s）" % pkg.get("license"))
    if not os.path.exists(os.path.join(BASE, "LICENSE")):
        warnings.append("根目录没有 LICENSE 文件")

    icon = os.path.join(BASE, "icon.png")
    if not os.path.exists(icon):
        problems.append("缺少 icon.png")
    else:
        size = png_size(icon)
        if not size or min(size) < 128:
            problems.append("icon.png 尺寸不足 128x128（当前 %s）" % (size,))
        else:
            ok.append("icon.png %dx%d" % size)

    missing = []
    for t in pkg.get("contributes", {}).get("themes", []):
        p = os.path.join(BASE, t["path"].lstrip("./"))
        if not os.path.exists(p):
            missing.append(t["path"])
    if missing:
        problems.append("主题文件缺失：%s" % ", ".join(missing))
    else:
        ok.append("%d 个主题文件齐全" % len(pkg.get("contributes", {}).get("themes", [])))

    print("发布前体检\n" + "=" * 60)
    for line in ok:
        print("  OK   " + line)
    for line in warnings:
        print("  WARN " + line)
    for line in problems:
        print("  FAIL " + line)

    print()
    if problems:
        print("结论：还有 %d 项必须修，修完再发。改 publish.ini 后重新跑 rebuild.bat。" % len(problems))
        return 1
    print("结论：可以发布。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
