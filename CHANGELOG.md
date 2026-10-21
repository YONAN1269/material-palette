# Changelog

## 1.4.0

### 新增

- **第 13 套主题：`Material Palette · Frost`（毛玻璃）**。参照 iOS 27 Liquid Glass 的材质规则做的一套**反向**配色 —— 不再追求一体化，而是强调层次：
  - 雾面玻璃面：侧栏 / 面板 / 标签栏 / 状态栏用「拌了冷白的半透明」`#2A2F37E6`，比编辑区亮一档
  - 1px 高光边：当前标签顶部 `#FFFFFF9E`，模拟上方光源的镜面反射
  - 高光外侧压暗描边 `#00000099`（iOS 27 相对 26 的改动，让玻璃有厚度）
  - 浮层半透明：补全框 / 悬浮提示 / 菜单底色带 alpha，能透出下面的代码
  - 焦点环恢复为 iOS 系统蓝 `#0A84FF8C`（一体化那批是关闭的）
  - 文字色一律不动：玻璃上的内容保持平、满对比
- 生成器新增 `frostify()`，新变体只在 `VARIANTS` 里加一个 `frost=True` 的条目，不改主流程。
- `preview.html` 支持毛玻璃卡片（奶白面 + 白色高光边，单独标 `FROST`）。

### 说明

- VS Code 主题没有 `backdrop-filter`，**做不到真实背景模糊**。Frost 是静态的「看起来像玻璃」，
  真透明度需配合窗口透明类扩展（如 Vibrancy）。

## 1.3.1

### 修复

- **赞赏码仍然裂图**：上一版把 vsix 内的 README 还原成相对路径，但 VS Code 的扩展详情页和扩展市场**只渲染绝对 https 图片地址**，相对路径照样裂。现在改为：打包时按 `publish.ini` 的 `IMAGES` 把 `assets/xxx` 替换成绝对地址（`scripts/inject_readme_images.py`），填一次地址即可长期生效。

### 新增

- **`publish.ini`**：发布配置集中到一个记事本文件（`IMAGES` / `REPO` / `PUBLISHER`），`rebuild.bat` 会自动写进 `package.json` 与打包后的 README，不用手改 JSON。
- **`publish.bat`**：一键「体检 → 打包 → 发布」，含 401 时获取 PAT 的引导。
- **`scripts/preflight.py`**：发布前体检，图片地址没填、publisher 还是 `local`、名字/描述超市场字符限制、图标尺寸不足、主题文件缺失都会拦住。
- `restart-code.bat` 已并入 `rebuild.bat` 结尾的询问，装完可直接重启。

## 1.3.0

### 修复

- **打包用了过期的文档**：1.2.0 的 vsix 里 `readme.md` 是旧版，图片指向 `https://github.com/your-name/...` 这种占位地址，所以扩展详情页里的赞赏码和总览图都加载不出来。现改为相对路径 `assets/...`，本地安装与扩展市场都能正常渲染。
- **强调色识别线过亮**：`tab.activeBorderTop` / `panelTitle.activeBorder` 原本是满色强调线，是全屏最亮的两条线，与"一体化"目标冲突。现按 `ACCENT_LINE = 0.6` 压一档（面板标题下沿再乘 0.6）。
- **活动栏左侧竖线去掉**：`activityBar.activeBorder` 置空，选中态靠 `activityBar.activeBackground` 的底色区分。

### 新增

- **`tune.ini`**：项目根目录的外部调参文件，记事本改三个数字即可（`SEAM` / `DIVIDER` / `ACCENT_LINE`），不用打开 Python 源码；生成器会读取它并覆盖默认值。
- **`restart-code.bat`**：一键「彻底关闭 VS Code → 重新启动」，解决装完没变化的问题（`reload window` 不会重新扫描扩展清单）。`rebuild.bat` 结尾也会询问是否立即重启。
- `scripts/diagnose.py` 体检脚本：列出磁盘上所有已安装副本、当前选中的主题、关键色槽取值，并对比 **VS Code 主进程启动时间 vs 扩展写入时间**，直接判定"为什么装了没变化"。
- `rebuild.bat` 增加体检步骤与重启提示（`Reload Window` 不会重新扫描扩展清单，必须完全退出应用）。

### 变更

- 新增旋钮 `ACCENT_LINE`（0 = 彻底平掉所有亮线，1.0 = Material 原味满色）。

## 1.2.0

对照官方 Material Theme (Equinusocio 34.7) 的真实取值重做了整套边框逻辑，修正 1.1.0 的方向性错误。

### 修复

- **分割线方向反了**：1.1.0 用前景色 5.5% 透明度画线，在深色底上等于**提亮**（`#0F111A` → `#171A24`，每个通道亮 50%），越调越像发光的边。现改为 `#00000030` 黑色压暗，与官方完全一致（浅色 `#00000020`）。
- **区域边框改为"不存在"**：`sideBar` / `panel` / `statusBar` / `titleBar` / `activityBar` 的 border 改用底色自身的半透明值（`#0F111A99`），叠加后仍是底色，数学上不产生线。
- **所有表面零色差**：侧栏、活动栏、状态栏、标签栏、终端面板与编辑区统一同一色值（`SEAM = 0`），不再有 1~2 级的下沉。
- **peek 视图边框**从强调色改为压暗阴影。
- **`focusBorder` 关闭**，不再额外描边。
- 修复 `editorGroupHeader.tabsBorder` 重复定义。

### 变更

- 主题名改为 `Material Palette · Ocean` 形式，避免与商店里的 Material Theme 在选择器里重名（`package.json` 的 themes 数组现由生成器自动回写）。
- 调节旋钮语义重定义：`SEAM`（区域下沉）、`DIVIDER`（黑色压暗强度），替换原来的 `HAIRLINE`。

### 新增

- `assets/wechat-pay.jpg` + README 赞赏区
- `PUBLISH.md` 发布到扩展市场的完整步骤
- `rebuild.bat` 一键「生成 → 校验 → 打包 → 安装」

## 1.1.0

- 首次尝试弱化分割线（方向有误，见 1.2.0）
- 外围区域下沉 10%~20% → 2.5%，标签栏与编辑区同色
- 缩进参考线 7%、空白字符 7%
- 预览页改为窗口示意

## 1.0.0

首个版本。

- 12 套 Material 风格配色：Default / Darker / Ocean / Palenight / Deep Forest / Nord / Lighter
- 5 套高对比变体（含 hc-black 与 hc-light）
- 每套 350+ 个 workbench 色槽，覆盖编辑器、侧边栏、标签页、终端、diff、通知、Git 装饰
- 语义高亮与语义 token 配色
- 深色系 / 浅色系两套独立语义调色板
