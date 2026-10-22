#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""体检：确认 VS Code 到底读到了哪个版本的 Material Palette。

回答三个最常见的问题：
  1. 磁盘上装的是哪个版本？（可能装了好几份，VS Code 只用其中一份）
  2. 当前窗口选的是哪套主题？
  3. 为什么「装了没变化」？—— 对比 VS Code 启动时间与扩展写入时间。

用法：python scripts/diagnose.py
"""
import json
import os
import subprocess
import sys
import time

EXT_ROOT = os.path.expanduser("~/.vscode/extensions")
USER_DIR = os.path.expanduser("~/AppData/Roaming/Code/User")
BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _publisher_prefix():
    """目录名前缀从 package.json 现取 —— 以前写死 local.material-palette-，
    发布者改成 YONAN1269 之后就再也匹配不上，误报「扩展没装上」。"""
    try:
        with open(os.path.join(BASE, "package.json"), encoding="utf-8") as f:
            pkg = json.load(f)
        return "%s.%s-" % (pkg["publisher"], pkg["name"])
    except Exception:
        return "material-palette-"


ID_PREFIX = _publisher_prefix()

# 这几条是全屏最亮的结构线，用来判断「新逻辑」是否生效
CHECK_KEYS = [
    "editor.background",
    "sideBar.background",
    "statusBar.background",
    "editorGroup.border",
    "sideBar.border",
    "panel.border",
    "tab.activeBorderTop",
    "panelTitle.activeBorder",
]


def hr(title=""):
    print("\n" + (("── %s " % title).ljust(66, "─") if title else "─" * 66))


def installed():
    if not os.path.isdir(EXT_ROOT):
        return []
    out = []
    for d in sorted(os.listdir(EXT_ROOT)):
        p = os.path.join(EXT_ROOT, d)
        if not d.lower().startswith(ID_PREFIX.lower()) or not os.path.isdir(p):
            continue
        pkg_path = os.path.join(p, "package.json")
        if not os.path.exists(pkg_path):
            out.append((d, None, None, p))
            continue
        try:
            pkg = json.load(open(pkg_path, encoding="utf-8"))
        except Exception:
            out.append((d, None, None, p))
            continue
        newest = 0
        for root, _, files in os.walk(p):
            for f in files:
                try:
                    newest = max(newest, os.path.getmtime(os.path.join(root, f)))
                except OSError:
                    pass
        out.append((d, pkg.get("version"), pkg.get("displayName"), p, newest))
    return out


def code_start():
    """VS Code 最早那个进程的启动时间（主进程）。拿不到就返回 None。"""
    if os.name != "nt":
        return None
    # 只取 .NET ticks 这种纯数字，避免中文 Windows 上 PowerShell 输出 GBK 日期导致解码失败
    cmd = [
        "powershell", "-NoProfile", "-NonInteractive", "-Command",
        "$p = Get-Process Code -ErrorAction SilentlyContinue | Sort-Object StartTime | "
        "Select-Object -First 1; if ($p) { $p.StartTime.ToUniversalTime().Ticks }",
    ]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, errors="replace",
                             timeout=25).stdout.strip()
        if not out.isdigit():
            return None
        return int(out) / 1e7 - 62135596800.0   # .NET ticks -> unix 时间戳
    except Exception:
        return None


def active_theme():
    """返回 [(来源, 主题名)]，含各个 Profile。"""
    res = []
    p = os.path.join(USER_DIR, "settings.json")
    if os.path.exists(p):
        try:
            s = json.load(open(p, encoding="utf-8"))
            res.append(("默认 Profile", s.get("workbench.colorTheme", "(未设置)")))
            cc = s.get("workbench.colorCustomizations") or {}
            if cc:
                keys = [k for k in cc if not k.startswith("[")]
                if keys:
                    res.append(("默认 Profile 全局覆盖", "%d 个键会盖住主题" % len(keys)))
        except Exception as e:
            res.append(("默认 Profile", "读不出来: %s" % e))

    prof_dir = os.path.join(USER_DIR, "profiles")
    if os.path.isdir(prof_dir):
        for root, _, files in os.walk(prof_dir):
            if "settings.json" in files:
                try:
                    s = json.load(open(os.path.join(root, "settings.json"), encoding="utf-8"))
                    res.append(("Profile " + os.path.basename(root),
                                s.get("workbench.colorTheme", "(继承默认)")))
                except Exception:
                    pass
    return res


def main():
    print("Material Palette 体检")
    print("扩展目录: %s" % EXT_ROOT)

    hr("1. 磁盘上安装了几份")
    items = installed()
    if not items:
        print("  没有找到任何已安装副本 —— 扩展没装上。")
        return 1
    for it in items:
        folder, ver, name, path = it[0], it[1], it[2], it[3]
        newest = it[4] if len(it) > 4 else 0
        when = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(newest)) if newest else "?"
        print("  %-36s v%-8s %s" % (folder, ver, name))
        print("  %-36s 文件写入 %s" % ("", when))
    if len(items) > 1:
        print("  ⚠ 有多份副本，VS Code 只认其中一份，建议删掉旧的。")

    hr("2. 当前选中的主题")
    for src, name in active_theme():
        print("  %-16s %s" % (src, name))

    hr("3. 主题里的关键色（判断是不是新版逻辑）")
    target = max(items, key=lambda x: x[4] if len(x) > 4 else 0)
    theme_dir = os.path.join(target[3], "themes")
    probe = None
    for cand in ("nord.json", "ocean.json"):
        if os.path.exists(os.path.join(theme_dir, cand)):
            probe = os.path.join(theme_dir, cand)
            break
    if probe:
        c = json.load(open(probe, encoding="utf-8"))["colors"]
        print("  样本: %s" % os.path.basename(probe))
        for k in CHECK_KEYS:
            print("    %-30s %s" % (k, c.get(k, "(未定义)")))
        flat = (c.get("sideBar.background") == c.get("editor.background")
                and c.get("editorGroup.border", "").upper().startswith("#000000"))
        print("  判定: %s" % ("✅ 一体化新版（区域同色 + 黑色压暗分隔）"
                             if flat else "❌ 旧版（区域还有色差，或分隔不是黑色阴影）"))
    else:
        print("  ⚠ 找不到主题文件，安装不完整。")

    hr("4. 为什么「装了没变化」")
    start = code_start()
    newest = target[4] if len(target) > 4 else 0
    if start is None:
        print("  没检测到正在运行的 VS Code（或取不到启动时间）。")
        print("  直接启动 VS Code 即可读到新版本。")
    else:
        print("  VS Code 主进程启动 : %s" % time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(start)))
        print("  扩展最新写入      : %s" % time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(newest)))
        if start < newest:
            print("\n  ❌ 结论：VS Code 是在扩展被写入**之前**启动的。")
            print("     扩展清单在启动时扫描一次并缓存在内存里，")
            print("     「Developer: Reload Window」不会重新扫描 —— 必须**完全退出并重新启动**。")
            print("     Windows：关闭所有窗口后，任务管理器里不能残留 Code.exe。")
        else:
            print("\n  ✅ 结论：VS Code 启动晚于扩展写入，当前窗口读到的就是这份。")

    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
