#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""主题自检：JSON 合法性、色值格式、清单一致性、前景/背景对比度。"""
import json
import os
import re

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
HEX = re.compile(r"^#[0-9A-Fa-f]{6}([0-9A-Fa-f]{2})?$")

fails = []


def lum(hexc):
    c = hexc.lstrip("#")[:6]
    out = []
    for i in (0, 2, 4):
        v = int(c[i:i + 2], 16) / 255
        out.append(v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4)
    return 0.2126 * out[0] + 0.7152 * out[1] + 0.0722 * out[2]


def ratio(a, b):
    la, lb = lum(a), lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


with open(os.path.join(BASE, "package.json"), encoding="utf-8") as f:
    pkg = json.load(f)

labels = set()
for entry in pkg["contributes"]["themes"]:
    path = os.path.join(BASE, entry["path"].replace("./", ""))
    if not os.path.exists(path):
        fails.append("缺少主题文件: " + entry["path"])
        continue
    if entry["label"] in labels:
        fails.append("主题名重复: " + entry["label"])
    labels.add(entry["label"])

    with open(path, encoding="utf-8") as f:
        t = json.load(f)

    if t.get("name") != entry["label"]:
        fails.append("%s: name 与清单不一致 (%s)" % (entry["path"], t.get("name")))

    bad = [k for k, v in t["colors"].items() if not HEX.match(str(v))]
    if bad:
        fails.append("%s: 非法色值 %s" % (entry["path"], bad[:5]))

    for i, rule in enumerate(t["tokenColors"]):
        if not rule.get("settings"):
            fails.append("%s: 第 %d 条 token 规则为空" % (entry["path"], i))

    r = ratio(t["colors"]["editor.foreground"], t["colors"]["editor.background"])
    light = t["type"] == "light"
    need = 7.0 if entry["uiTheme"].startswith("hc") else 4.5
    flag = "OK " if r >= need else "LOW"
    print("%-4s %-42s %5.2f:1  (%d colors, %d rules)"
          % (flag, entry["label"], r, len(t["colors"]), len(t["tokenColors"])))
    if r < need:
        fails.append("%s: 正文对比度 %.2f 低于 %.1f" % (entry["label"], r, need))

    # 选中行 / 侧边栏文字对比度
    r2 = ratio(t["colors"]["sideBar.foreground"], t["colors"]["sideBar.background"])
    if r2 < 3.0:
        fails.append("%s: 侧边栏对比度 %.2f 偏低" % (entry["label"], r2))

print()
if fails:
    print("FAILED %d" % len(fails))
    for x in fails:
        print("  - " + x)
    raise SystemExit(1)
print("全部 %d 个主题通过校验" % len(labels))
