#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""设计验收用：拿真实 theme.json 渲染一个窗口示意图，Chrome headless 截图。

用法：
    python scripts/qa_render.py frost          # 生成 _qa/<id>.html
    python scripts/qa_render.py frost --shot    # 顺带截图（需要 Chrome）

不属于插件产物（.vscodeignore 已排除 *.py / _qa），只是给我自己看效果用的。
"""
import json
import os
import subprocess
import sys

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

SYNTAX = {"c": "#546E7A", "k": "#C792EA", "p": "#A6B3C4", "s": "#C3E88D",
          "n": "#F78C6C", "f": "#82AAFF", "v": "#EEFFFF", "t": "#FFCB6B",
          "o": "#89DDFF"}

LINES = [
    [("c", "// frosted glass \u2014 iOS 27 liquid glass")],
    [("k", "import"), ("p", " { createGlass } "), ("k", "from"), ("s", " './material'"), ("p", ";")],
    [("k", "const"), ("p", " surface "), ("o", "="), ("p", " "), ("f", "createGlass"),
     ("p", "({ blur: "), ("n", "24"), ("p", ", saturate: "), ("n", "1.8"), ("p", " });")],
    [("k", "on"), ("p", "("), ("t", "scroll"), ("p", ", ("), ("v", "y"), ("p", ") {")],
    [("p", "  surface."), ("f", "translateY"), ("p", "("), ("o", "-"), ("v", "y"),
     ("p", " * "), ("n", "0.35"), ("p", ");")],
    [("p", "  surface."), ("f", "setOpacity"), ("p", "("), ("n", "0.84"), ("p", ");")],
    [("p", "});")],
]


def css(c):
    c = c.lstrip("#")
    if len(c) == 8:
        r, g, b, a = (int(c[i:i + 2], 16) for i in (0, 2, 4, 6))
        return "rgba(%d,%d,%d,%.3f)" % (r, g, b, a / 255)
    return "#" + c


def row(chunks, n):
    seg = []
    for kind, text in chunks:
        text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        seg.append('<span style="color:%s">%s</span>'
                   % (SYNTAX.get(kind, "#E9EEF6"), text.replace(" ", "&nbsp;")))
    return '<div class="l"><span class="ln">%d</span>%s</div>' % (n, "".join(seg))


def render(tid):
    with open(os.path.join(BASE, "themes", tid + ".json"), encoding="utf-8") as f:
        C = json.load(f)["colors"]

    rows = "".join(row(ch, i + 1) for i, ch in enumerate(LINES))
    html = TEMPLATE.format(
        backdrop=css(C["editor.background"]),
        title=css(C["titleBar.activeBackground"]),
        act=css(C["activityBar.background"]),
        side=css(C["sideBar.background"]),
        sidefg=css(C["sideBar.foreground"]),
        panel=css(C["panel.background"]),
        status=css(C["statusBar.background"]),
        tabsbg=css(C["editorGroupHeader.tabsBackground"]),
        tabon=css(C["tab.activeBackground"]),
        bg=css(C["editor.background"]),
        glass=css(C["editorSuggestWidget.background"]),
        glass2=css(C["editorHoverWidget.background"]),
        rim=css(C["sideBar.border"]),
        rimHi=css(C["tab.activeBorderTop"]),
        edge=css(C["editorGroup.border"]),
        fg=css(C["foreground"]),
        accent=css(C["button.background"]),
        sel=css(C["list.activeSelectionBackground"]),
        sel2=css(C["list.focusBackground"]),
        rows=rows,
    )
    out_dir = os.path.join(BASE, "_qa")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, tid + ".html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    return out


TEMPLATE = """<!DOCTYPE html><html><head><meta charset="utf-8"><style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#04060A;padding:24px;font:13px/1.5 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif}}
.win{{width:1180px;height:720px;display:flex;flex-direction:column;border-radius:12px;overflow:hidden;
     box-shadow:0 30px 70px rgba(0,0,0,.65);background:{backdrop}}}
.title{{height:36px;background:{title};display:flex;align-items:center;padding:0 14px;gap:8px;
       border-bottom:1px solid {rim};color:{fg};font-size:12px}}
.dots{{display:flex;gap:6px;margin-right:10px}}
.dots i{{width:10px;height:10px;border-radius:50%;display:block;background:#4A5160}}
.body{{flex:1;display:flex;min-height:0}}
.act{{width:52px;background:{act};border-right:1px solid {rim};padding:14px 0;
      display:flex;flex-direction:column;align-items:center;gap:16px}}
.act i{{width:20px;height:20px;border-radius:6px;background:{fg};opacity:.28}}
.act i.on{{opacity:.95;background:{accent}}}
.side{{width:250px;background:{side};border-right:1px solid {rim};padding:12px 0;color:{sidefg}}}
.side h4{{font-size:11px;letter-spacing:.1em;color:{fg};opacity:.55;padding:0 14px 8px;font-weight:600}}
.side div{{padding:4px 14px;font-size:12px}}
.side div.sel{{background:{sel}}}
.main{{flex:1;display:flex;flex-direction:column;min-width:0;background:{bg}}}
.tabs{{display:flex;background:{tabsbg};border-bottom:1px solid {edge}}}
.tab{{padding:7px 16px;font-size:12px;color:{fg};opacity:.45}}
.tab.on{{opacity:.95;background:{tabon};box-shadow:inset 0 2px 0 0 {rimHi};border-right:1px solid {rim}}}
.ed{{flex:1;position:relative;padding:12px 0 0 0;font:12.5px/1.78 ui-monospace,Consolas,monospace;
     color:{fg};overflow:hidden}}
.l{{white-space:pre}}
.ln{{display:inline-block;width:28px;text-align:right;margin-right:14px;color:{fg};opacity:.25}}
.widget{{position:absolute;left:196px;top:112px;width:440px;background:{glass};
        border:1px solid {rim};border-radius:10px;box-shadow:0 18px 44px rgba(0,0,0,.55);overflow:hidden}}
.widget .row{{padding:6px 12px;font:12px ui-monospace,Consolas,monospace;color:{fg};opacity:.92}}
.widget .row.sel{{background:{sel2}}}
.widget .row b{{color:{accent};font-weight:600}}
.hover{{position:absolute;left:520px;top:300px;width:330px;background:{glass2};
       border:1px solid {rim};border-radius:10px;box-shadow:0 20px 50px rgba(0,0,0,.6);padding:8px 12px;
       color:{fg}}}
.hover .h1{{font:12px ui-monospace,Consolas,monospace;opacity:.95;margin-bottom:4px}}
.hover .h2{{font:11.5px/1.6 -apple-system,sans-serif;opacity:.7}}
.panel{{height:150px;background:{panel};border-top:1px solid {rim};color:{fg};
       font:12px/1.7 ui-monospace,Consolas,monospace;padding:8px 14px}}
.panel .ph{{font-family:-apple-system,sans-serif;font-size:11px;opacity:.5;margin-bottom:6px}}
.status{{height:24px;background:{status};border-top:1px solid {rim};color:{fg};opacity:.7;
        font-size:11px;display:flex;align-items:center;justify-content:space-between;padding:0 12px}}
</style></head><body>
<div class="win">
  <div class="title"><span class="dots"><i></i><i></i><i></i></span>glass.ts — material-palette</div>
  <div class="body">
    <div class="act"><i class="on"></i><i></i><i></i><i></i><i></i></div>
    <div class="side">
      <h4>EXPLORER</h4>
      <div class="sel">glass.ts</div>
      <div>palette.json</div>
      <div>preview.html</div>
      <div>README.md</div>
      <div>tune.ini</div>
    </div>
    <div class="main">
      <div class="tabs"><div class="tab on">glass.ts</div><div class="tab">palette.json</div></div>
      <div class="ed">
        {rows}
        <div class="widget">
          <div class="row sel"><b>createGlass</b>  (options: GlassOptions) =&gt; Surface</div>
          <div class="row">glassify</div>
          <div class="row">createLayer</div>
        </div>
        <div class="hover">
          <div class="h1">GlassOptions<span style="opacity:.55">: interface</span></div>
          <div class="h2">blur?: number — 背景模糊半径，24 是常用值<br>saturate?: number — 饱和度，1.8 起</div>
        </div>
      </div>
      <div class="panel"><div class="ph">TERMINAL</div>&gt; pnpm dev<br>ready on :5173</div>
    </div>
  </div>
  <div class="status"><span>main*</span><span>TypeScript · UTF-8</span></div>
</div>
</body></html>"""


def main():
    tid = sys.argv[1] if len(sys.argv) > 1 else "frost"
    out = render(tid)
    print("wrote", out)
    if "--shot" in sys.argv:
        png = os.path.join(BASE, "_qa", tid + ".png")
        subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                        "--force-device-scale-factor=2",
                        "--screenshot=" + png, "--window-size=1240,780",
                        "file:///" + out.replace("\\", "/")],
                       check=False, capture_output=True)
        print("shot", png)


if __name__ == "__main__":
    main()
