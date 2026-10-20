#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Material Palette - VSCode 主题生成器

用一套调色板规格批量生成多套 Material 风格主题，保证所有变体的
语义配色（关键字 / 字符串 / 函数 / 类型 ...）完全一致，只切换底层底色。
同时输出 preview.html 供肉眼比对。
"""
import json
import os
import struct
import zlib

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
THEMES = os.path.join(BASE, "themes")
os.makedirs(THEMES, exist_ok=True)


# ---------------------------------------------------------------- color utils
def hx(c):
    return c.lstrip("#")


def rgb(c):
    c = hx(c)[:6]
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def tohex(t):
    return "#%02X%02X%02X" % tuple(max(0, min(255, round(x))) for x in t)


def mix(a, b, t):
    ra, rb = rgb(a), rgb(b)
    return tohex(tuple(ra[i] + (rb[i] - ra[i]) * t for i in range(3)))


def lighten(c, t):
    return mix(c, "#FFFFFF", t)


def darken(c, t):
    return mix(c, "#000000", t)


def alpha(c, a):
    return "#%s%02X" % (hx(c)[:6].upper(), max(0, min(255, round(a * 255))))


# ---------------------------------------------------------------- 一体化调节
# 参照官方 Material Theme (Equinusocio 34.7) 的真实取值，两个旋钮：
#
# SEAM —— 外围区域（侧栏/活动栏/状态栏/标签栏/面板）相对编辑区底色的下沉幅度。
#        官方是 0：所有表面字面意义上同一个颜色，区域之间零色差。
#        0      = 与官方一致，整个窗口一张连续的纸（默认）
#        0.03   = 只有贴脸细看才分得出侧栏
#        0.08   = 常规主题那种明显的块状分区
SEAM = 0.0
#
# DIVIDER —— 分隔阴影强度，**用黑色压暗**，不是提亮。
#        官方 editorGroup.border = #00000030（黑 19%）、浅色 #00000020（黑 12%）。
#        深色底上「更暗的线」看起来是凹进去的阴影，「更亮的线」是发光的边——后者永远显眼。
#        0      = 完全没有线
#        0.19   = 与官方一致（默认）
#        0.35   = 能明确看出分组边界
DIVIDER = 0.19
#
# ACCENT_LINE —— 强调色识别线（当前标签顶部、面板标题下沿、活动栏左侧）的透明度。
#        这几条是全屏**最亮**的线，也是「一体化」最容易被破坏的地方。
#        0      = 完全不要识别线，纯靠底色差异区分（最平）
#        0.6    = 保留一点识别度（默认）
#        1.0    = 满色强调线（Material 原味）
ACCENT_LINE = 0.6


# ---------------------------------------------------------------- 外部调参文件
# 上面三个值是「默认值」。项目根目录下有个 tune.ini，改那里的数字会覆盖它们。
# 这样不用打开代码，用记事本改三个数字、双击 rebuild.bat 就行。
def _load_tune():
    global SEAM, DIVIDER, ACCENT_LINE
    path = os.path.join(BASE, "tune.ini")
    if not os.path.exists(path):
        return
    mapping = {"SEAM": "SEAM", "DIVIDER": "DIVIDER", "ACCENT_LINE": "ACCENT_LINE"}
    for raw in open(path, encoding="utf-8-sig"):
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith(";") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip().upper()
        num_text = val.split("#")[0].split(";")[0].strip()
        if key not in mapping:
            print("  ! tune.ini: 不认识的参数 %s，已忽略" % key)
            continue
        try:
            num = float(num_text)
        except ValueError:
            print("  ! tune.ini: %s 的值 '%s' 不是数字，已忽略" % (key, num_text))
            continue
        if key == "SEAM":
            SEAM = max(0.0, min(1.0, num))
        elif key == "DIVIDER":
            DIVIDER = max(0.0, min(1.0, num))
        else:
            ACCENT_LINE = max(0.0, min(1.0, num))
    print("  读取 tune.ini -> SEAM=%s  DIVIDER=%s  ACCENT_LINE=%s"
          % (SEAM, DIVIDER, ACCENT_LINE))


_load_tune()

# ---------------------------------------------------------------- token colors
DARK = {
    "comment": "#546E7A",
    "string": "#C3E88D",
    "number": "#F78C6C",
    "constant": "#FF9CAC",
    "keyword": "#C792EA",
    "func": "#82AAFF",
    "var": "#EEFFFF",
    "type": "#FFCB6B",
    "prop": "#80CBC4",
    "operator": "#89DDFF",
    "tag": "#F07178",
    "attribute": "#C792EA",
    "regex": "#89DDFF",
    "escape": "#89DDFF",
    "invalid": "#FF5370",
    "decorator": "#82AAFF",
    "builtin": "#FFCB6B",
    "markup": "#C792EA",
    "inserted": "#C3E88D",
    "deleted": "#FF5370",
    "changed": "#FFCB6B",
}

LIGHT = {
    "comment": "#AABFC9",
    "string": "#91B859",
    "number": "#F76D47",
    "constant": "#F76D47",
    "keyword": "#7C4DFF",
    "func": "#6182B8",
    "var": "#546E7A",
    "type": "#F6A434",
    "prop": "#39ADB5",
    "operator": "#39ADB5",
    "tag": "#F07178",
    "attribute": "#7C4DFF",
    "regex": "#39ADB5",
    "escape": "#39ADB5",
    "invalid": "#E53935",
    "decorator": "#6182B8",
    "builtin": "#F6A434",
    "markup": "#7C4DFF",
    "inserted": "#91B859",
    "deleted": "#E53935",
    "changed": "#F6A434",
}


def tokens(p):
    C = p

    def r(scope, fg=None, style=None):
        s = {}
        if fg:
            s["foreground"] = fg
        if style is not None:
            s["fontStyle"] = style
        return {"scope": scope if isinstance(scope, list) else [scope], "settings": s}

    T = [
        # reset
        r(["comment", "punctuation.definition.comment"], C["comment"], "italic"),
        r(["string", "string.quoted", "string.template", "punctuation.definition.string"],
          C["string"]),
        r(["string.regexp", "string.regexp.js", "punctuation.definition.string.regexp"],
          C["regex"]),
        r(["constant.character.escape", "string.quoted.double .constant.character.escape",
           "punctuation.definition.template-expression"], C["escape"]),
        r(["constant.numeric", "constant.other.symbol", "keyword.other.unit"], C["number"]),
        r(["constant.language", "constant.language.boolean", "constant.language.null",
           "constant.language.undefined"], C["constant"]),
        r(["constant.other", "variable.other.constant", "entity.name.constant",
           "support.constant"], C["constant"]),

        # keywords
        r(["keyword", "keyword.control", "keyword.other", "keyword.control.flow",
           "keyword.control.import", "keyword.control.module"], C["keyword"]),
        r(["storage", "storage.type", "storage.modifier"], C["keyword"]),
        r(["keyword.operator", "punctuation.accessor", "punctuation.separator",
           "punctuation.terminator"], C["operator"]),
        r(["keyword.operator.new", "keyword.operator.expression", "keyword.operator.typeof",
           "keyword.operator.instanceof", "keyword.operator.logical"], C["keyword"]),
        r("keyword.operator.assignment", C["operator"]),

        # functions
        r(["entity.name.function", "support.function", "meta.function-call",
           "entity.name.function.member", "variable.function"], C["func"]),
        r("entity.name.function.decorator", C["decorator"]),
        r(["meta.decorator", "punctuation.decorator"], C["decorator"], "italic"),

        # types / classes
        r(["entity.name.type", "entity.name.class", "entity.other.inherited-class",
           "support.class", "support.type", "support.type.primitive",
           "entity.name.type.class", "entity.name.type.interface",
           "entity.name.type.enum", "entity.name.type.struct",
           "entity.name.type.alias", "entity.name.type.module"], C["type"]),
        r(["entity.name.namespace", "entity.name.scope-resolution",
           "punctuation.separator.namespace"], C["type"]),
        r(["entity.name.type.parameter", "variable.parameter.type", "storage.type.generic"],
           C["type"], "italic"),

        # variables
        r(["variable", "variable.other", "variable.other.readwrite",
           "variable.other.object", "meta.definition.variable"], C["var"]),
        r(["variable.parameter", "variable.parameter.function"], C["var"]),
        r(["variable.language", "variable.language.this", "variable.language.self",
           "variable.language.super"], C["keyword"], "italic"),
        r(["variable.other.object.property", "variable.other.property",
           "meta.object-literal.key", "support.type.property-name",
           "support.variable.property"], C["prop"]),
        r(["entity.name.label", "punctuation.definition.label"], C["keyword"]),

        # markup tags / attributes
        r(["entity.name.tag", "punctuation.definition.tag"], C["tag"]),
        r(["entity.other.attribute-name", "entity.other.attribute-name.class",
           "entity.other.attribute-name.id"], C["attribute"], "italic"),
        r(["entity.name.tag.custom", "support.class.component",
           "entity.name.type.component", "support.class.component.jsx",
           "support.class.component.tsx"], C["type"]),

        # embedded: css / scss / less
        r(["support.type.property-name.css", "meta.property-name.css",
           "meta.property-name.scss", "meta.property-name.less"], C["prop"]),
        r(["meta.property-value.css", "support.constant.property-value.css",
           "meta.property-value.scss", "support.constant.property-value.scss"], C["string"]),
        r(["entity.other.attribute-name.class.css", "entity.other.attribute-name.id.css",
           "entity.other.attribute-name.pseudo-class.css",
           "entity.other.attribute-name.pseudo-element.css",
           "entity.other.attribute-name.parent-selector.css"], C["type"]),
        r(["variable.parameter.url.css", "support.constant.font-name.css"], C["number"]),

        # json / yaml / toml
        r(["support.type.property-name.json", "meta.structure.dictionary.json .string"],
          C["prop"]),
        r(["entity.name.tag.yaml", "support.type.property-name.yaml"], C["prop"]),
        r(["punctuation.definition.block.sequence.item.yaml",
           "punctuation.separator.key-value.yaml"], C["operator"]),
        r(["entity.name.tag.toml", "support.type.property-name.toml"], C["prop"]),
        r(["punctuation.definition.table.toml"], C["keyword"]),

        # markdown
        r(["markup.heading", "markup.heading entity.name", "punctuation.definition.heading"],
          C["keyword"], "bold"),
        r("markup.bold", C["type"], "bold"),
        r("markup.italic", C["type"], "italic"),
        r(["markup.strikethrough", "markup.strikethrough punctuation.definition"], None,
          "strikethrough"),
        r(["markup.inline.raw", "markup.fenced_code", "markup.raw",
           "punctuation.definition.raw"], C["string"]),
        r(["markup.underline.link", "string.other.link", "constant.other.reference.link"],
          C["func"]),
        r(["markup.quote", "punctuation.definition.quote"], C["comment"], "italic"),
        r(["markup.list", "punctuation.definition.list"], C["operator"]),
        r("markup.inserted", C["inserted"]),
        r("markup.deleted", C["deleted"]),
        r("markup.changed", C["changed"]),

        # diff
        r("diff.header", C["operator"]),
        r("diff.inserted", C["inserted"]),
        r("diff.deleted", C["deleted"]),

        # python / ruby / rust / go specifics
        r(["support.function.builtin", "support.type.builtin", "support.class.builtin",
           "support.constant.builtin"], C["builtin"]),
        r(["entity.name.type.class.python", "entity.name.function.decorator.python"],
          C["func"]),
        r(["variable.parameter.function.language.special.self.python",
           "variable.language.special.self.python"], C["keyword"], "italic"),
        r(["storage.type.function.arrow.ts", "storage.type.function.ts"], C["keyword"]),
        r(["entity.name.type.ts", "entity.name.type.alias.ts", "meta.type.annotation.ts"],
          C["type"]),
        r(["keyword.control.directive.include.cpp", "keyword.control.preprocessor.cpp",
           "meta.preprocessor"], C["keyword"]),
        r(["entity.name.function.macro", "meta.macro"], C["func"]),
        r(["storage.modifier.lifetime.rust", "entity.name.lifetime.rust",
           "punctuation.definition.lifetime.rust"], C["keyword"], "italic"),
        r(["keyword.other.rust", "storage.type.rust"], C["keyword"]),
        r(["support.type.package-name.rust", "entity.name.type.module.rust"], C["type"]),

        # shell
        r(["support.function.builtin.shell", "variable.other.normal.shell"], C["func"]),
        r(["punctuation.definition.variable.shell", "punctuation.definition.evaluation.shell"],
          C["operator"]),

        # misc
        r(["punctuation.definition.template-expression.begin",
           "punctuation.definition.template-expression.end"], C["operator"]),
        # css 单位 / 数值
        r(["keyword.other.unit", "constant.numeric.css", "constant.numeric.scss"], C["number"]),
        r(["support.function.misc.css", "support.function.transform.css"], C["func"]),
        r(["variable.scss", "variable.other.scss", "variable.other.less"], C["constant"]),

        # c / c++ / c# / java
        r(["entity.name.type.struct.c", "entity.name.type.enum.c",
           "entity.name.type.class.cpp", "entity.name.type.struct.cpp"], C["type"]),
        r(["keyword.control.directive.pragma.cpp", "keyword.control.directive.define.cpp"],
           C["keyword"]),
        r(["meta.preprocessor.string", "string.quoted.double.include"], C["string"]),
        r(["storage.type.annotation.java", "storage.modifier.annotation.java"],
           C["decorator"]),

        # php / ruby
        r(["variable.other.php", "punctuation.definition.variable.php"], C["var"]),
        r(["support.function.construct.php", "support.function.builtin.php"], C["builtin"]),
        r(["entity.name.type.class.ruby", "variable.other.constant.ruby"], C["type"]),

        # sql
        r(["keyword.other.DML.sql", "keyword.other.DDL.sql",
           "keyword.other.create.sql", "keyword.other.order.sql"], C["keyword"]),
        r(["constant.other.database-name.sql", "constant.other.table-name.sql"],
           C["type"]),

        # markdown 表格 / 分隔线
        r(["markup.table.header", "punctuation.separator.table-cell"], C["type"]),
        r(["punctuation.definition.horizontal-rule"], C["comment"]),

        r(["invalid", "invalid.illegal"], C["invalid"], "underline"),
        r(["invalid.deprecated"], C["invalid"], "strikethrough"),
        r(["meta.embedded.block.frontmatter", "punctuation.definition.frontmatter"],
          C["comment"]),
        r(["fenced_code.block.language", "markup.fenced_code.block.language"],
          C["type"]),
        r(["entity.other.attribute-name.jsx", "entity.other.attribute-name.tsx"],
          C["attribute"]),
        r(["punctuation.definition.tag.begin.jsx", "punctuation.definition.tag.end.jsx",
           "punctuation.definition.tag.begin.tsx", "punctuation.definition.tag.end.tsx"],
          C["tag"]),
    ]
    return T


def semantic(p):
    return {
        "namespace": {"foreground": p["type"]},
        "type": {"foreground": p["type"]},
        "class": {"foreground": p["type"]},
        "enum": {"foreground": p["type"]},
        "interface": {"foreground": p["type"]},
        "struct": {"foreground": p["type"]},
        "typeParameter": {"foreground": p["type"], "fontStyle": "italic"},
        "parameter": {"foreground": p["var"]},
        "variable": {"foreground": p["var"]},
        "variable.readonly": {"foreground": p["constant"]},
        "property": {"foreground": p["prop"]},
        "enumMember": {"foreground": p["constant"]},
        "event": {"foreground": p["func"]},
        "function": {"foreground": p["func"]},
        "method": {"foreground": p["func"]},
        "macro": {"foreground": p["keyword"]},
        "keyword": {"foreground": p["keyword"]},
        "modifier": {"foreground": p["keyword"]},
        "comment": {"foreground": p["comment"], "fontStyle": "italic"},
        "string": {"foreground": p["string"]},
        "number": {"foreground": p["number"]},
        "regexp": {"foreground": p["regex"]},
        "operator": {"foreground": p["operator"]},
        "decorator": {"foreground": p["decorator"]},
        "label": {"foreground": p["keyword"]},
    }


# ---------------------------------------------------------------- variants
VARIANTS = [
    dict(id="default", label="Material Palette · Default", ui="vs-dark",
         bg="#263238", fg="#EEFFFF", pal=DARK, accent="#82AAFF"),
    dict(id="darker", label="Material Palette · Darker", ui="vs-dark",
         bg="#212121", fg="#EEFFFF", pal=DARK, accent="#82AAFF"),
    dict(id="ocean", label="Material Palette · Ocean", ui="vs-dark",
         bg="#0F111A", fg="#A6ACCD", pal=DARK, accent="#82AAFF"),
    dict(id="palenight", label="Material Palette · Palenight", ui="vs-dark",
         bg="#292D3E", fg="#A6ACCD", pal=DARK, accent="#82AAFF"),
    dict(id="deep-forest", label="Material Palette · Deep Forest", ui="vs-dark",
         bg="#0D1F17", fg="#B2CCD6", pal=DARK, accent="#C3E88D"),
    dict(id="nord", label="Material Palette · Nord", ui="vs-dark",
         bg="#2E3440", fg="#D8DEE9", pal=DARK, accent="#88C0D0"),
    dict(id="lighter", label="Material Palette · Lighter", ui="vs",
         bg="#FAFAFA", fg="#546E7A", pal=LIGHT, accent="#6182B8", light=True),
    dict(id="default-hc", label="Material Palette · High Contrast", ui="hc-black",
         bg="#1A2327", fg="#FFFFFF", pal=DARK, accent="#82AAFF", hc=True),
    dict(id="darker-hc", label="Material Palette · Darker High Contrast", ui="hc-black",
         bg="#000000", fg="#FFFFFF", pal=DARK, accent="#82AAFF", hc=True),
    dict(id="ocean-hc", label="Material Palette · Ocean High Contrast", ui="hc-black",
         bg="#090B10", fg="#FFFFFF", pal=DARK, accent="#82AAFF", hc=True),
    dict(id="palenight-hc", label="Material Palette · Palenight High Contrast", ui="hc-black",
         bg="#1B1E2B", fg="#FFFFFF", pal=DARK, accent="#82AAFF", hc=True),
    dict(id="lighter-hc", label="Material Palette · Lighter High Contrast", ui="hc-light",
         bg="#FFFFFF", fg="#37474F", pal=LIGHT, accent="#4527A0", light=True, hc=True),
]

# 终端 16 色
ANSI_DARK = ["#000000", "#F07178", "#C3E88D", "#FFCB6B", "#82AAFF", "#C792EA",
             "#89DDFF", "#EEFFFF"]
ANSI_DARK_BRIGHT = ["#4A4A4A", "#FF8B92", "#D6F5A3", "#FFE082", "#9BBFFF",
                    "#D0A9F5", "#A4E9FF", "#FFFFFF"]
ANSI_LIGHT = ["#546E7A", "#E53935", "#91B859", "#F6A434", "#6182B8", "#7C4DFF",
              "#39ADB5", "#263238"]
ANSI_LIGHT_BRIGHT = ["#78909C", "#EF5350", "#A5C261", "#FFB300", "#7B9FD4",
                     "#9673F5", "#4DB6BF", "#1C262B"]


def build(v):
    bg = v["bg"]
    fg = v["fg"]
    p = v["pal"]
    light = v.get("light", False)
    hc = v.get("hc", False)
    accent = v["accent"]

    # ---- 表面：SEAM=0 时与编辑区字面同色（官方 Material 的做法）
    if light:
        side = mix(bg, "#000000", SEAM * 0.6)
        panel = bg
        widget = "#FFFFFF"
        hover = mix(bg, "#000000", 0.04)
        fgdim = mix(fg, bg, 0.22)
        gutter = mix(fg, bg, 0.55)
        fg_side = mix(fg, bg, 0.04)
        tab_inactive = bg
        ruler = mix(bg, "#000000", 0.04)
        ansi = ANSI_LIGHT
        ansi_b = ANSI_LIGHT_BRIGHT
    else:
        side = bg if hc else mix(bg, "#000000", SEAM)
        panel = bg
        widget = lighten(bg, 0.06)
        hover = alpha(fg, 0.06)
        fgdim = mix(fg, bg, 0.36)
        gutter = mix(fg, bg, 0.58)
        fg_side = fg if hc else mix(fg, bg, 0.16)
        tab_inactive = bg
        ruler = alpha(fg, 0.07)
        ansi = ANSI_DARK
        ansi_b = ANSI_DARK_BRIGHT

    # 三类边框，语义完全不同，不能混用：
    #   region  —— 区域分隔（侧栏/状态栏/标题栏/面板）。用底色自身半透明，
    #              混出来仍是底色 = 视觉上不存在，和官方 #0F111A60 等价。
    #   divider —— 真正的分隔阴影（编辑分组 / peek / diff）。黑色压暗，
    #              只会让边界「陷进去」，不会发光。
    #   border  —— 浮层/输入框描边。极淡的前景色，官方是 #FFFFFF10。
    if hc:
        border = lighten(bg, 0.26) if not light else mix(bg, "#000000", 0.30)
        divider = border
        region = border
    else:
        border = alpha(fg, 0.06) if not light else alpha("#000000", 0.06)
        divider = alpha("#000000", DIVIDER if not light else DIVIDER * 0.65)
        region = alpha(bg, 0.6)

    sel = alpha(accent, 0.22 if not light else 0.16)
    sel_inactive = alpha(accent, 0.10 if not light else 0.08)
    sel_hl = alpha(accent, 0.14)
    word_hl = alpha(accent, 0.16)

    colors = {
        "focusBorder": alpha(accent, 0.0),
        "foreground": fg,
        "descriptionForeground": fgdim,
        "errorForeground": p["invalid"],
        "icon.foreground": fgdim,
        "selection.background": sel,

        # editor
        "editor.background": bg,
        "editor.foreground": fg,
        "editorLineNumber.foreground": gutter,
        "editorLineNumber.activeForeground": accent,
        "editorCursor.foreground": accent,
        "editor.selectionBackground": sel,
        "editor.inactiveSelectionBackground": sel_inactive,
        "editor.selectionHighlightBackground": sel_hl,
        "editor.selectionHighlightBorder": alpha(accent, 0.0),
        "editor.wordHighlightBackground": word_hl,
        "editor.wordHighlightStrongBackground": alpha(accent, 0.24),
        "editor.wordHighlightBorder": alpha(accent, 0.35),
        "editor.findMatchBackground": alpha(p["type"], 0.32),
        "editor.findMatchHighlightBackground": alpha(p["type"], 0.18),
        "editor.findMatchBorder": alpha(p["type"], 0.0),
        "editor.findRangeHighlightBackground": alpha(accent, 0.10),
        "editor.hoverHighlightBackground": alpha(accent, 0.14),
        "editor.lineHighlightBackground": lighten(bg, 0.03) if not light else darken(bg, 0.03),
        "editor.lineHighlightBorder": alpha(accent, 0.0),
        "editor.rangeHighlightBackground": alpha(accent, 0.08),
        "editorWhitespace.foreground": alpha(fg, 0.07),
        "editorIndentGuide.background1": alpha(fg, 0.07),
        "editorIndentGuide.activeBackground1": alpha(fg, 0.16),
        "editorRuler.foreground": ruler,
        "editorCodeLens.foreground": gutter,
        "editorBracketMatch.background": alpha(accent, 0.16),
        "editorBracketMatch.border": alpha(accent, 0.55),
        "editorGutter.background": bg,
        "editorGutter.modifiedBackground": alpha(p["changed"], 0.75),
        "editorGutter.addedBackground": alpha(p["inserted"], 0.75),
        "editorGutter.deletedBackground": alpha(p["invalid"], 0.75),
        "editorGutter.foldingControlForeground": fgdim,
        "editorLink.activeForeground": accent,
        "editorError.foreground": p["invalid"],
        "editorWarning.foreground": p["type"],
        "editorInfo.foreground": p["func"],
        "editorHint.foreground": p["comment"],
        "editorLightBulb.foreground": p["type"],
        "editorLightBulbAutoFix.foreground": p["func"],
        "editorBreadcrumb.background": bg,

        "editorOverviewRuler.border": alpha(bg, 0.0),
        "editorOverviewRuler.findMatchForeground": alpha(p["type"], 0.85),
        "editorOverviewRuler.rangeHighlightForeground": alpha(accent, 0.35),
        "editorOverviewRuler.selectionHighlightForeground": alpha(accent, 0.6),
        "editorOverviewRuler.wordHighlightForeground": alpha(accent, 0.4),
        "editorOverviewRuler.errorForeground": p["invalid"],
        "editorOverviewRuler.warningForeground": p["type"],
        "editorOverviewRuler.infoForeground": p["func"],
        "editorOverviewRuler.modifiedForeground": alpha(p["changed"], 0.8),
        "editorOverviewRuler.addedForeground": alpha(p["inserted"], 0.8),
        "editorOverviewRuler.deletedForeground": alpha(p["invalid"], 0.8),
        "editorOverviewRuler.bracketMatchForeground": alpha(accent, 0.8),

        "editorBracketHighlight.foreground1": p["type"],
        "editorBracketHighlight.foreground2": p["keyword"],
        "editorBracketHighlight.foreground3": p["func"],
        "editorBracketHighlight.foreground4": p["operator"],
        "editorBracketHighlight.foreground5": p["tag"],
        "editorBracketHighlight.foreground6": p["string"],
        "editorBracketHighlight.unexpectedBracket.foreground": p["invalid"],
        "editorBracketPairGuide.background1": alpha(p["type"], 0.16),
        "editorBracketPairGuide.background2": alpha(p["keyword"], 0.16),
        "editorBracketPairGuide.background3": alpha(p["func"], 0.16),
        "editorBracketPairGuide.activeBackground1": alpha(p["type"], 0.4),
        "editorBracketPairGuide.activeBackground2": alpha(p["keyword"], 0.4),
        "editorBracketPairGuide.activeBackground3": alpha(p["func"], 0.4),

        "editorInlayHint.background": alpha(fg, 0.06),
        "editorInlayHint.foreground": fgdim,
        "editorInlayHint.typeForeground": alpha(p["type"], 0.8),
        "editorInlayHint.parameterForeground": alpha(fg, 0.55),
        "editorStickyScroll.background": lighten(bg, 0.03) if not light else darken(bg, 0.03),
        "editorStickyScrollHover.background": hover,

        # suggestions / widgets
        "editorSuggestWidget.background": widget,
        "editorSuggestWidget.border": border,
        "editorSuggestWidget.foreground": fg,
        "editorSuggestWidget.selectedBackground": hover,
        "editorSuggestWidget.highlightForeground": accent,
        "editorSuggestWidget.focusHighlightForeground": p["type"],
        "editorHoverWidget.background": widget,
        "editorHoverWidget.border": border,
        "editorHoverWidget.foreground": fg,
        "editorHoverWidget.highlightForeground": accent,
        "editorHoverWidget.statusBarBackground": lighten(widget, 0.03) if not light else darken(widget, 0.03),
        "editorWidget.background": widget,
        "editorWidget.border": border,
        "editorWidget.foreground": fg,
        "editorWidget.resizeBorder": accent if hc else alpha(accent, 0.55),
        "editorGhostText.foreground": alpha(fg, 0.35),
        "editorCommentsWidget.resolvedBorder": alpha(p["inserted"], 0.6),
        "editorCommentsWidget.unresolvedBorder": alpha(p["type"], 0.6),

        # activity bar / sidebar
        "activityBar.background": side,
        "activityBar.foreground": fg,
        "activityBar.inactiveForeground": alpha(fg, 0.45),
        "activityBar.border": border if hc else region,
        "activityBar.activeBorder": alpha(accent, 0.0),
        "activityBar.activeBackground": alpha(accent, 0.10),
        "activityBarBadge.background": accent,
        "activityBarBadge.foreground": "#0B0E14" if not light else "#FFFFFF",
        "activityBarTop.foreground": fg,

        "auxiliaryBar.background": side,
        "auxiliaryBar.foreground": fg_side,
        "auxiliaryBar.border": border if hc else region,

        "sideBar.background": side,
        "sideBar.foreground": fg_side,
        "sideBar.border": border if hc else region,
        "sideBarTitle.foreground": fg,
        "sideBarSectionHeader.background": alpha(fg, 0.04),
        "sideBarSectionHeader.foreground": fg,
        "sideBarSectionHeader.border": divider if hc else alpha(fg, 0.03),
        "sideBarActivityBarTop.border": alpha(border, 0.0),

        "list.activeSelectionBackground": hover,
        "list.activeSelectionForeground": fg,
        "list.inactiveSelectionBackground": alpha(fg, 0.05),
        "list.inactiveSelectionForeground": fgdim,
        "list.hoverBackground": alpha(fg, 0.05),
        "list.hoverForeground": fg,
        "list.focusBackground": alpha(accent, 0.16),
        "list.focusForeground": fg,
        "list.focusOutline": alpha(accent, 0.0),
        "list.highlightForeground": accent,
        "list.errorForeground": p["invalid"],
        "list.warningForeground": p["type"],
        "list.deemphasizedForeground": fgdim,
        "list.filterMatchBackground": alpha(p["type"], 0.22),
        "list.filterMatchBorder": alpha(p["type"], 0.0),
        "tree.indentGuidesStroke": alpha(fg, 0.14),
        "tree.inactiveIndentGuidesStroke": alpha(fg, 0.06),

        # status bar
        "statusBar.background": side,
        "statusBar.foreground": fg_side,
        "statusBar.border": border if hc else region,
        "statusBar.noFolderBackground": side,
        "statusBar.noFolderForeground": fgdim,
        "statusBar.debuggingBackground": p["invalid"],
        "statusBar.debuggingForeground": "#0B0E14" if not light else "#FFFFFF",
        "statusBar.debuggingBorder": alpha(border, 0.0),
        "statusBarItem.hoverBackground": alpha(fg, 0.10),
        "statusBarItem.activeBackground": alpha(fg, 0.14),
        "statusBarItem.prominentBackground": alpha(fg, 0.10),
        "statusBarItem.remoteBackground": accent,
        "statusBarItem.remoteForeground": "#0B0E14" if not light else "#FFFFFF",
        "statusBarItem.errorBackground": alpha(p["invalid"], 0.9),
        "statusBarItem.warningBackground": alpha(p["type"], 0.9),

        # title bar / menu
        "titleBar.activeBackground": side,
        "titleBar.activeForeground": fg,
        "titleBar.inactiveBackground": side,
        "titleBar.inactiveForeground": alpha(fg, 0.45),
        "titleBar.border": border if hc else region,
        "menubar.selectionBackground": hover,
        "menubar.selectionForeground": fg,
        "menubar.selectionBorder": alpha(border, 0.0),
        "menu.background": widget,
        "menu.foreground": fg,
        "menu.border": border,
        "menu.selectionBackground": alpha(accent, 0.18),
        "menu.selectionForeground": fg,
        "menu.selectionBorder": alpha(accent, 0.0),
        "menu.separatorBackground": border,

        # tabs
        "tabs.background": tab_inactive,
        "tab.activeBackground": bg,
        "tab.activeForeground": fg,
        "tab.inactiveBackground": tab_inactive,
        "tab.inactiveForeground": alpha(fg, 0.45),
        "tab.border": border if hc else bg,
        "tab.activeBackground": bg,
        "tab.unfocusedActiveBackground": bg,
        "tab.activeBorder": alpha(accent, 0.0),
        "tab.activeBorderTop": alpha(accent, ACCENT_LINE),
        "tab.unfocusedActiveBorderTop": alpha(accent, 0.4),
        "tab.hoverBackground": hover,
        "tab.hoverForeground": fg,
        "tab.unfocusedHoverBackground": hover,
        "tab.activeModifiedBorder": alpha(p["changed"], 0.8),
        "tab.inactiveModifiedBorder": alpha(p["changed"], 0.4),
        "editorGroupHeader.tabsBackground": tab_inactive,
        "editorGroupHeader.noTabsBackground": bg,
        "editorGroup.border": divider,
        "editorGroup.dropBackground": alpha(accent, 0.12),
        "editorGroupHeader.border": border if hc else alpha(bg, 0.0),
        "editorGroupHeader.tabsBorder": region if hc else alpha(bg, 0.0),
        "editorGroup.emptyBackground": bg,

        # panel / terminal
        "panel.background": bg,
        "panel.border": region,
        "panel.dropBorder": accent,
        "panelTitle.activeForeground": fg,
        "panelTitle.inactiveForeground": alpha(fg, 0.45),
        "panelTitle.activeBorder": alpha(accent, ACCENT_LINE * 0.6),
        "panelSection.border": divider if hc else alpha(fg, 0.03),
        "panelSectionHeader.background": alpha(fg, 0.05),
        "panelSectionHeader.foreground": fg,
        "terminal.background": bg,
        "terminal.foreground": fg,
        "terminal.border": region,
        "terminalCursor.foreground": accent,
        "terminal.selectionBackground": sel,
        "terminal.ansiBlack": ansi[0],
        "terminal.ansiRed": ansi[1],
        "terminal.ansiGreen": ansi[2],
        "terminal.ansiYellow": ansi[3],
        "terminal.ansiBlue": ansi[4],
        "terminal.ansiMagenta": ansi[5],
        "terminal.ansiCyan": ansi[6],
        "terminal.ansiWhite": ansi[7],
        "terminal.ansiBrightBlack": ansi_b[0],
        "terminal.ansiBrightRed": ansi_b[1],
        "terminal.ansiBrightGreen": ansi_b[2],
        "terminal.ansiBrightYellow": ansi_b[3],
        "terminal.ansiBrightBlue": ansi_b[4],
        "terminal.ansiBrightMagenta": ansi_b[5],
        "terminal.ansiBrightCyan": ansi_b[6],
        "terminal.ansiBrightWhite": ansi_b[7],

        # buttons / inputs
        "button.background": accent,
        "button.foreground": "#0B0E14" if not light else "#FFFFFF",
        "button.hoverBackground": lighten(accent, 0.12),
        "button.secondaryBackground": alpha(fg, 0.12),
        "button.secondaryForeground": fg,
        "button.secondaryHoverBackground": alpha(fg, 0.18),
        "input.background": lighten(bg, 0.04) if not light else "#FFFFFF",
        "input.foreground": fg,
        "input.border": border,
        "input.placeholderForeground": alpha(fg, 0.40),
        "inputOption.activeBackground": alpha(accent, 0.25),
        "inputOption.activeForeground": fg,
        "inputOption.activeBorder": accent,
        "inputValidation.errorBackground": alpha(p["invalid"], 0.9),
        "inputValidation.errorBorder": p["invalid"],
        "dropdown.background": widget,
        "dropdown.foreground": fg,
        "dropdown.border": border,
        "dropdown.listBackground": widget,
        "badge.background": accent,
        "badge.foreground": "#0B0E14" if not light else "#FFFFFF",
        "progressBar.background": accent,
        "checkbox.background": lighten(bg, 0.06) if not light else "#FFFFFF",
        "checkbox.border": border,
        "checkbox.foreground": fg,

        # scrollbar / minimap
        "scrollbar.shadow": alpha("#000000", 0.0) if not light else alpha("#000000", 0.08),
        "scrollbarSlider.background": alpha(fg, 0.14),
        "scrollbarSlider.hoverBackground": alpha(fg, 0.22),
        "scrollbarSlider.activeBackground": alpha(fg, 0.30),
        "minimap.background": bg,
        "minimap.selectionHighlight": alpha(accent, 0.28),
        "minimap.findMatchHighlight": alpha(p["type"], 0.45),
        "minimap.errorHighlight": alpha(p["invalid"], 0.7),
        "minimap.warningHighlight": alpha(p["type"], 0.7),
        "minimapGutter.addedBackground": alpha(p["inserted"], 0.7),
        "minimapGutter.modifiedBackground": alpha(p["changed"], 0.7),
        "minimapGutter.deletedBackground": alpha(p["invalid"], 0.7),
        "minimapSlider.background": alpha(fg, 0.10),
        "minimapSlider.hoverBackground": alpha(fg, 0.16),
        "minimapSlider.activeBackground": alpha(fg, 0.22),

        # breadcrumb
        "breadcrumb.background": bg,
        "breadcrumb.foreground": alpha(fg, 0.55),
        "breadcrumb.focusForeground": fg,
        "breadcrumb.activeSelectionForeground": accent,
        "breadcrumbPicker.background": widget,

        # peek view
        "peekView.border": border if hc else divider,
        "peekViewEditor.background": lighten(bg, 0.03) if not light else darken(bg, 0.02),
        "peekViewEditor.matchHighlightBackground": alpha(p["type"], 0.28),
        "peekViewResult.background": side,
        "peekViewResult.fileForeground": fg,
        "peekViewResult.lineForeground": fgdim,
        "peekViewResult.matchHighlightBackground": alpha(p["type"], 0.28),
        "peekViewResult.selectionBackground": alpha(accent, 0.20),
        "peekViewResult.selectionForeground": fg,
        "peekViewTitle.background": widget,
        "peekViewTitleLabel.foreground": fg,
        "peekViewTitleDescription.foreground": fgdim,

        # notifications
        "notifications.background": widget,
        "notifications.foreground": fg,
        "notifications.border": border,
        "notificationCenterHeader.background": widget,
        "notificationCenterHeader.foreground": fg,
        "notificationsErrorIcon.foreground": p["invalid"],
        "notificationsWarningIcon.foreground": p["type"],
        "notificationsInfoIcon.foreground": p["func"],

        # quick input / command center
        "quickInput.background": widget,
        "quickInput.foreground": fg,
        "quickInputList.focusBackground": hover,
        "quickInputList.focusForeground": fg,
        "quickInputList.focusIconForeground": accent,
        "commandCenter.background": side,
        "commandCenter.foreground": fgdim,
        "commandCenter.activeBackground": hover,
        "commandCenter.activeForeground": fg,
        "commandCenter.border": border if hc else alpha(fg, 0.12),
        "keybindingLabel.background": alpha(fg, 0.08),
        "keybindingLabel.foreground": fgdim,
        "keybindingLabel.border": border if hc else alpha(fg, 0.12),
        "keybindingLabel.bottomBorder": border if hc else alpha(fg, 0.12),

        # git decoration
        "gitDecoration.addedResourceForeground": p["inserted"],
        "gitDecoration.modifiedResourceForeground": p["type"],
        "gitDecoration.deletedResourceForeground": p["invalid"],
        "gitDecoration.untrackedResourceForeground": p["string"],
        "gitDecoration.ignoredResourceForeground": alpha(fg, 0.38),
        "gitDecoration.conflictingResourceForeground": p["keyword"],
        "gitDecoration.renamedResourceForeground": p["func"],
        "gitDecoration.stageModifiedResourceForeground": p["type"],
        "gitDecoration.stageDeletedResourceForeground": p["invalid"],
        "gitDecoration.submoduleResourceForeground": alpha(fg, 0.45),

        # diff / merge
        "diffEditor.insertedTextBackground": alpha(p["inserted"], 0.14),
        "diffEditor.removedTextBackground": alpha(p["invalid"], 0.14),
        "diffEditor.insertedLineBackground": alpha(p["inserted"], 0.08),
        "diffEditor.removedLineBackground": alpha(p["invalid"], 0.08),
        "diffEditor.border": divider,
        "diffEditor.diagonalFill": alpha(fg, 0.06),
        "merge.currentHeaderBackground": alpha(p["func"], 0.35),
        "merge.currentContentBackground": alpha(p["func"], 0.14),
        "merge.incomingHeaderBackground": alpha(p["inserted"], 0.35),
        "merge.incomingContentBackground": alpha(p["inserted"], 0.14),
        "merge.commonHeaderBackground": alpha(fg, 0.18),
        "merge.commonContentBackground": alpha(fg, 0.08),
        "merge.border": alpha(border, 0.0),

        # settings
        "settings.headerForeground": fg,
        "settings.modifiedItemIndicator": accent,
        "settings.dropdownBackground": widget,
        "settings.dropdownForeground": fg,
        "settings.dropdownBorder": border,
        "settings.checkboxBackground": lighten(bg, 0.06) if not light else "#FFFFFF",
        "settings.checkboxForeground": fg,
        "settings.checkboxBorder": border,
        "settings.textInputBackground": lighten(bg, 0.04) if not light else "#FFFFFF",
        "settings.textInputForeground": fg,
        "settings.textInputBorder": border,
        "settings.numberInputBackground": lighten(bg, 0.04) if not light else "#FFFFFF",
        "settings.numberInputForeground": fg,
        "settings.numberInputBorder": border,
        "settings.focusedRowBackground": alpha(accent, 0.06),
        "settings.rowHoverBackground": alpha(accent, 0.04),

        # welcome / misc
        "welcomePage.background": bg,
        "welcomePage.tileBackground": lighten(bg, 0.04) if not light else "#FFFFFF",
        "welcomePage.tileHoverBackground": hover,
        "welcomePage.progress.background": alpha(fg, 0.10),
        "welcomePage.progress.foreground": accent,
        "debugToolBar.background": widget,
        "debugToolBar.border": alpha(border, 0.0),
        "editor.stackFrameHighlightBackground": alpha(p["type"], 0.22),
        "editor.focusedStackFrameHighlightBackground": alpha(p["inserted"], 0.22),
        "symbolIcon.classForeground": p["type"],
        "symbolIcon.functionForeground": p["func"],
        "symbolIcon.variableForeground": p["var"],
        "symbolIcon.stringForeground": p["string"],
        "symbolIcon.numberForeground": p["number"],
        "symbolIcon.keywordForeground": p["keyword"],
        "symbolIcon.commentForeground": p["comment"],
        "editorError.background": alpha(p["invalid"], 0.0),
        "activityBar.dropBorder": accent,
        "ports.iconRunningProcessForeground": p["string"],
    }

    if hc:
        colors["contrastBorder"] = border
        colors["contrastActiveBorder"] = accent
        colors["editor.findMatchBorder"] = alpha(p["type"], 0.7)
        colors["editorCursor.foreground"] = "#FFFFFF" if not light else "#000000"
        colors["statusBar.border"] = border
        colors["titleBar.border"] = border
        colors["sideBar.border"] = border
        colors["panel.border"] = border
        colors["tab.border"] = border

    return {
        "name": v["label"],
        "type": "light" if light else "dark",
        "semanticHighlighting": True,
        "$schema": "vscode://schemas/color-theme",
        "colors": colors,
        "tokenColors": tokens(p),
        "semanticTokenColors": semantic(p),
    }


# ---------------------------------------------------------------- icon
def make_icon(path, size=256):
    """圆角方形渐变底 + 三条 Material 强调色色带。"""
    px = [[(0, 0, 0, 0) for _ in range(size)] for _ in range(size)]
    top = rgb("#2E3D45")
    bottom = rgb("#161E23")
    r = size * 0.22
    stripes = [rgb("#C792EA"), rgb("#82AAFF"), rgb("#C3E88D")]
    for y in range(size):
        for x in range(size):
            # 圆角遮罩
            cx = min(x, size - 1 - x)
            cy = min(y, size - 1 - y)
            if cx < r and cy < r:
                dx, dy = r - cx, r - cy
                if dx * dx + dy * dy > r * r:
                    continue
            t = y / (size - 1)
            col = [top[i] + (bottom[i] - top[i]) * t for i in range(3)]
            # 斜向色带（右下角）
            d = (x + y) - size * 1.05
            for i, sc in enumerate(stripes):
                lo = i * size * 0.085
                hi = lo + size * 0.055
                if lo <= d < hi:
                    k = 1 - (d - lo) / (hi - lo) * 0.35
                    col = [col[j] + (sc[j] - col[j]) * k for j in range(3)]
            px[y][x] = (int(col[0]), int(col[1]), int(col[2]), 255)

    raw = b""
    for row in px:
        raw += b"\x00" + b"".join(struct.pack("BBBB", *p) for p in row)

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw, 9))
    png += chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)


# ---------------------------------------------------------------- preview
SAMPLE = [
    [("c", "// material palette \u2014 12 variants")],
    [("k", "import"), ("p", " { defineTheme } "), ("k", "from"),
     ("s", " 'material'"), ("p", ";")],
    [("k", "const"), ("p", " palette "), ("o", "="), ("p", " { ocean: "),
     ("s", "'#0F111A'"), ("p", " };")],
    [],
    [("k", "async function"), ("f", " greet"), ("p", "("), ("v", "name"),
     ("p", ": "), ("t", "string"), ("p", ") {")],
    [("p", "  "), ("k", "const"), ("p", " msg "), ("o", "="),
     ("p", " `Hello, "), ("e", "${name}"), ("p", "!`;")],
    [("p", "  "), ("k", "return"), ("p", " "), ("v", "console"), ("p", "."),
     ("f", "log"), ("p", "(msg, "), ("n", "42"), ("p", ", "),
     ("cl", "true"), ("p", ");")],
    [("p", "}")],
]

PAL_KEY = {"c": "comment", "k": "keyword", "s": "string", "n": "number",
           "f": "func", "v": "var", "t": "type", "o": "operator",
           "e": "escape", "cl": "constant"}


def preview_html(variants):
    """颜色总览。刻意画出「一体化」窗口：侧栏 / 标签栏 / 状态栏与编辑区同色。"""
    cards = []
    for v in variants:
        p = v["pal"]
        light = v.get("light", False)
        bg = v["bg"]
        fg = v["fg"]
        side = mix(bg, "#000000", SEAM * 0.6 if light else SEAM)
        accent = v["accent"]
        rows = []
        for idx, line in enumerate(SAMPLE):
            if not line:
                rows.append('<div class="bl">&nbsp;</div>')
                continue
            seg = []
            for kind, text in line:
                color = p[PAL_KEY[kind]] if kind in PAL_KEY else fg
                style = "font-style:italic" if kind == "c" else ""
                esc = (text.replace("&", "&amp;").replace("<", "&lt;")
                       .replace(">", "&gt;").replace(" ", "&nbsp;"))
                seg.append(f'<span style="color:{color};{style}">{esc}</span>')
            rows.append(f'<div><span class="ln">{idx + 1}</span>'
                        f'{"".join(seg)}</div>')
        swatches = "".join(
            f'<i style="background:{p[k]}" title="{k}"></i>'
            for k in ["keyword", "func", "string", "number", "type", "constant",
                      "prop", "operator", "tag", "comment"])
        cards.append(f"""
        <section class="card" style="--bg:{bg};--side:{side};--fg:{fg};--accent:{accent}">
          <header>
            <div>
              <h2>{v['label']}</h2>
              <code>{v['id']}.json · {v['ui']}</code>
            </div>
            <div class="chip">{'LIGHT' if light else 'DARK'}</div>
          </header>
          <div class="win">
            <div class="rail"><i class="on"></i><i></i><i></i><i></i></div>
            <div class="pane">
              <div class="tabs">
                <span class="on">index.ts</span><span>palette.json</span>
              </div>
              <div class="code">{"".join(rows)}</div>
              <div class="status"><span>main*</span><span>UTF-8 · TypeScript</span></div>
            </div>
          </div>
          <div class="meta">
            <div class="sw">{swatches}</div>
            <div class="hex">{bg} <span>·</span> {accent}</div>
          </div>
        </section>""")

    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>Material Palette · 主题总览</title>
<style>
  *{{box-sizing:border-box}}
  body{{margin:0;padding:40px 32px 64px;background:#0B0F13;color:#E6EDF3;
       font:14px/1.6 -apple-system,"Segoe UI",system-ui,"Microsoft YaHei",sans-serif}}
  .hd{{max-width:1240px;margin:0 auto 34px}}
  .hd h1{{font-size:26px;margin:0 0 8px;letter-spacing:-.4px}}
  .hd p{{margin:0;color:#7D8B96}}
  .hd b{{color:#82AAFF;font-weight:600}}
  .grid{{max-width:1240px;margin:0 auto;display:grid;gap:22px;
        grid-template-columns:repeat(auto-fill,minmax(380px,1fr))}}
  .card{{background:var(--bg);border:1px solid rgba(128,140,150,.16);
        border-radius:14px;overflow:hidden;display:flex;flex-direction:column}}
  header{{display:flex;justify-content:space-between;align-items:flex-start;
          padding:14px 16px 10px;background:var(--side);gap:10px}}
  header h2{{margin:0;font-size:14.5px;color:var(--fg);font-weight:600}}
  header code{{font-size:11px;color:var(--fg);opacity:.42;
              font-family:ui-monospace,Consolas,monospace}}
  .chip{{font-size:9.5px;letter-spacing:.12em;padding:3px 8px;border-radius:999px;
        border:1px solid currentColor;color:var(--fg);opacity:.4;flex:none}}
  .win{{display:flex;min-height:0}}
  .rail{{width:26px;background:var(--side);padding:9px 0;display:flex;
        flex-direction:column;align-items:center;gap:10px;flex:none}}
  .rail i{{width:11px;height:11px;border-radius:3px;background:var(--fg);
          opacity:.16;display:block}}
  .rail i.on{{background:var(--accent);opacity:.95;
             box-shadow:0 0 0 2px rgba(255,255,255,.04)}}
  .pane{{flex:1;min-width:0;background:var(--bg)}}
  .tabs{{display:flex;font-size:11px;background:var(--bg);
        font-family:ui-monospace,Consolas,monospace}}
  .tabs span{{padding:5px 12px 4px;color:var(--fg);opacity:.4;flex:none}}
  .tabs span.on{{opacity:.95;box-shadow:inset 0 2px 0 0 color-mix(in srgb,var(--accent) {int(ACCENT_LINE*100)}%,transparent)}}
  .code{{padding:8px 14px 6px;font:12px/1.72 ui-monospace,Consolas,"Courier New",monospace;
        color:var(--fg);white-space:pre;overflow:auto}}
  .ln{{display:inline-block;width:20px;text-align:right;margin-right:12px;
      color:var(--fg);opacity:.3;user-select:none}}
  .bl{{height:1.72em}}
  .status{{display:flex;justify-content:space-between;padding:2px 10px;
          font-size:10px;background:var(--side);color:var(--fg);opacity:.5}}
  .meta{{margin-top:auto;padding:10px 14px 13px;display:flex;justify-content:space-between;
        align-items:center;border-top:1px solid rgba(128,140,150,.16)}}
  .sw{{display:flex;gap:5px}}
  .sw i{{width:11px;height:11px;border-radius:3px;display:block}}
  .hex{{font:11px ui-monospace,Consolas,monospace;color:var(--fg);opacity:.42}}
  .hex span{{opacity:.4;margin:0 3px}}
</style></head><body>
<div class="hd">
  <h1>Material Palette · VSCode 主题</h1>
  <p>共 <b>{len(variants)}</b> 套配色。侧栏、标签栏、状态栏与编辑区 <b>同一底色</b>，
     区域之间零色差；唯一的分割是 <b>#00000030</b> 的压暗阴影 —— 整个窗口是一张连续的纸。</p>
</div>
<div class="grid">{"".join(cards)}</div>
</body></html>"""


# ---------------------------------------------------------------- main
def main():
    manifest = []
    for v in VARIANTS:
        theme = build(v)
        path = os.path.join(THEMES, v["id"] + ".json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(theme, f, indent=2, ensure_ascii=False)
        manifest.append({
            "label": v["label"],
            "uiTheme": v["ui"],
            "path": "./themes/%s.json" % v["id"],
        })
        print("generated %-18s %5d color keys, %3d token rules"
              % (v["id"], len(theme["colors"]), len(theme["tokenColors"])))

    with open(os.path.join(BASE, "themes", "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    # 把清单回写 package.json，避免主题名/路径与生成结果不一致
    pkg_path = os.path.join(BASE, "package.json")
    with open(pkg_path, encoding="utf-8") as f:
        pkg = json.load(f)
    pkg.setdefault("contributes", {})["themes"] = manifest
    with open(pkg_path, "w", encoding="utf-8") as f:
        json.dump(pkg, f, indent=2, ensure_ascii=False)
        f.write("\n")

    make_icon(os.path.join(BASE, "icon.png"))
    with open(os.path.join(BASE, "preview.html"), "w", encoding="utf-8") as f:
        f.write(preview_html(VARIANTS))
    print("icon.png + preview.html ready")


if __name__ == "__main__":
    main()
