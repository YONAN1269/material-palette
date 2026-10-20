#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""读取 publish.ini，把 REPO / PUBLISHER 写进 package.json。

为什么要这一步：package.json 是 JSON，手动改容易漏逗号、引号，
而且 publisher / repository / bugs / homepage 要四处一致。
这里统一从 publish.ini 读，避免出错。
"""
import io
import json
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INI = os.path.join(BASE, "publish.ini")


def read_ini(path):
    data = {}
    if not os.path.exists(path):
        return data
    for raw in open(path, encoding="utf-8-sig"):
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith(";") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        val = val.split(" #")[0].split(";")[0].strip()
        data[key.strip().upper()] = val
    return data


def main():
    cfg = read_ini(INI)
    images = cfg.get("IMAGES", "")
    repo = cfg.get("REPO", "").rstrip("/")
    publisher = cfg.get("PUBLISHER", "")

    pkg_path = os.path.join(BASE, "package.json")
    pkg = json.load(io.open(pkg_path, encoding="utf-8"))
    changed = []

    if publisher and pkg.get("publisher") != publisher:
        pkg["publisher"] = publisher
        changed.append("publisher = %s" % publisher)

    if repo:
        want = {"type": "git", "url": repo}
        if pkg.get("repository") != want:
            pkg["repository"] = want
            changed.append("repository = %s" % repo)
        bugs = {"url": repo + "/issues"}
        if pkg.get("bugs") != bugs:
            pkg["bugs"] = bugs
            changed.append("bugs")
        home = repo + "#readme"
        if pkg.get("homepage") != home:
            pkg["homepage"] = home
            changed.append("homepage")

    if changed:
        with io.open(pkg_path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(pkg, f, indent=2, ensure_ascii=False)
            f.write("\n")
        print("publish.ini -> package.json 已更新: " + ", ".join(changed))
    else:
        print("publish.ini -> package.json 无需改动")

    if not images:
        print("  提示：publish.ini 的 IMAGES 还是空的 —— 扩展详情页里的赞赏码会裂图")
    if not publisher:
        print("  提示：PUBLISHER 还是空的，当前 publisher = %s（只能本地安装，不能发布）"
              % pkg.get("publisher"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
