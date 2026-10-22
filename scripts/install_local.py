#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把打好的 vsix 解包到本机 VS Code 扩展目录。

为什么不用 `code --install-extension`：VS Code 装在需要提权的目录时，
CLI 在普通终端里会静默失败（退出码 0、无输出、不报错），很难排查。
直接解包到用户自己的 extensions 目录是等价的，且不需要管理员权限。
"""
import json
import os
import shutil
import sys
import zipfile


def register(root, pkg, folder):
    """把扩展写进 extensions.json。

    新版 VS Code 以 extensions.json 为唯一清单：只把文件夹解包进去，
    主题选择器里根本看不到（表现为「装了没变化」）。之前这里漏了，
    是 1.4.0 一度装完不出现的真正原因。
    """
    ext_json = os.path.join(root, "extensions.json")
    try:
        with open(ext_json, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = []

    eid = "%s.%s" % (pkg["publisher"].lower(), pkg["name"].lower())
    template, kept = None, []
    for e in data:
        if e.get("identifier", {}).get("id", "").lower() == eid:
            template = e          # 旧版本的条目，拿来当 URI 结构模板
            continue
        kept.append(e)

    if template:
        old = template.get("relativeLocation", "")

        def swap(o):
            if isinstance(o, dict):
                return {k: swap(v) for k, v in o.items()}
            if isinstance(o, list):
                return [swap(x) for x in o]
            if isinstance(o, str) and old and old in o:
                return o.replace(old, folder)
            return o

        entry = swap(template)
        entry["version"] = pkg["version"]
    else:
        fs = os.path.join(root, folder)
        posix = fs.replace("\\", "/")
        entry = {
            "identifier": {"id": eid},
            "version": pkg["version"],
            "location": {
                "$mid": 1,
                "fsPath": fs,
                "_sep": 1,
                "external": "file:///" + posix[0].lower() + posix[1:].replace(":", "%3A"),
                "path": "/" + posix[0].lower() + posix[1:],
                "scheme": "file",
            },
            "relativeLocation": folder,
        }

    kept.append(entry)
    with open(ext_json, "w", encoding="utf-8") as f:
        json.dump(kept, f, indent=2)
    print("registered in extensions.json: %s@%s" % (eid, pkg["version"]))


def main(vsix):
    if not os.path.exists(vsix):
        print("vsix not found:", vsix)
        return 1

    with zipfile.ZipFile(vsix) as z:
        pkg = json.loads(z.read("extension/package.json").decode("utf-8"))
        folder = "%s.%s-%s" % (pkg["publisher"], pkg["name"], pkg["version"])

        roots = [os.path.expanduser("~/.vscode/extensions")]
        extra = os.environ.get("VSCODE_EXT_DIR")
        if extra:
            roots.insert(0, extra)

        target = os.path.join(roots[0], folder)
        if os.path.exists(target):
            shutil.rmtree(target)
        os.makedirs(target)

        for name in z.namelist():
            if not name.startswith("extension/") or name.endswith("/"):
                continue
            rel = name[len("extension/"):]
            out = os.path.join(target, rel)
            os.makedirs(os.path.dirname(out), exist_ok=True)
            with z.open(name) as src, open(out, "wb") as dst:
                shutil.copyfileobj(src, dst)

    # 顺手把同 ID 的旧版本标成待清理，避免 VS Code 里出现两个版本
    root = roots[0]
    for d in os.listdir(root):
        if not d.startswith("%s.%s-" % (pkg["publisher"], pkg["name"])) or d == folder:
            continue
        try:
            shutil.rmtree(os.path.join(root, d))
            print("removed old version:", d)
        except OSError as e:
            print("could not remove %s (%s), VS Code will ignore it" % (d, e))

    print("installed %s -> %s" % (folder, target))
    register(root, pkg, folder)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "material-palette-1.2.0.vsix"))
