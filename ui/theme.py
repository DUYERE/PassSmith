"""全局主题 - 精密仪器感双配色 + 整体缩放的 QSS 构建

配色沿用原方案：深色为深海军蓝（#0b1220 系），浅色为冷灰白（#eef1f7 系）；
蓝 #4d8dff 作强调（焦点/选中/读数），绿 #10b981 作主操作。
深色靠表面亮度分层（bg → card → card_hover），不用阴影（QSS 不支持 box-shadow）。

保留的结构性改进：字阶 11 / 12 / 13 / 15 / 18（相邻级差足够大）、
圆角 4px 控件 / 8px 卡片、主按钮纯色去渐变、重点分组左侧强调条。

缩放原理：所有尺寸/字号均以基准像素 * scale 计算，
切换缩放或主题时重建整套样式表，实现全局 UI 缩放与换肤。
"""

import os

from core.util import app_base_dir, resolve_resource_dir

PROJECT_ROOT = app_base_dir()
# 打包后优先 exe 同级的 assets/，回退内置副本
ASSET_DIR = resolve_resource_dir('assets')

CHECK_IMG = os.path.join(ASSET_DIR, 'check.png').replace('\\', '/')
ARROW_DARK_THEME = os.path.join(ASSET_DIR, 'arrow_down.png').replace('\\', '/')
ARROW_LIGHT_THEME = os.path.join(ASSET_DIR, 'arrow_down_dark.png').replace('\\', '/')
APP_ICON = os.path.join(ASSET_DIR, 'favicon.ico')

# 可选缩放档位
ZOOM_STEPS = [0.8, 0.9, 1.0, 1.15, 1.3, 1.5, 1.75, 2.0]
DEFAULT_ZOOM = 1.0

DEFAULT_THEME = 'dark'
THEMES = ('dark', 'light')

# 字阶（基准像素，实际渲染时乘缩放系数）
FONT_XS = 11      # 辅助说明、占位提示
FONT_SM = 12      # 次要标签、元数据
FONT_BASE = 13    # 正文、输入框、按钮
FONT_MD = 15      # 分组标题、区块标题
FONT_LG = 18      # 关键数字（预估条数）

# 圆角梯度：仪器感偏低，不用大圆角
RADIUS_SM = 4
RADIUS_MD = 8

# 主题调色板：QSS 中所有颜色均取自此处，新增主题只需补一套键值
# 括号内为 OKLCH 源值，便于后续微调时保持感知均匀
PALETTES = {
    'dark': dict(
        bg="#0b1220",            # 窗口底色（深海军蓝）
        bg_soft="#0e1729",       # 输入框/控制台凹陷面
        card="#121c31",          # 卡片
        card_hover="#17233d",
        card_hi="#17233d",       # 重点分组表面
        emphasis_bg="#17233d",   # 重点分组背景
        border="#243353",
        border_hi="#33507f",
        text="#e8eefc",
        muted="#8fa0c0",
        faint="#6f83a8",         # 占位符：比 muted 暗但仍可读
        accent="#4d8dff",        # 蓝：焦点、选中、读数
        accent_deep="#2f6fe0",
        accent_text="#ffffff",
        green="#10b981",         # 绿：主操作按钮
        green_deep="#0b8f66",
        green_hover="#22c58f",
        red="#e5484d",
        red_deep="#b3383c",
        warn="#f0a020",
        btn_bg="#1a2743",
        btn_border="#2c3f68",
        btn_hover="#223156",
        btn_pressed="#18233f",
        btn_disabled_bg="#141d33",
        btn_disabled_border="#243353",
        btn_disabled_text="#5a688a",
        btn_text="#dbe6ff",
        scroll_handle="#2c3f68",
        console_bg="#0a0f1c",
        console_text="#d7e3ff",
        disclaimer_text="#ffd479",
        indicator_border="#3a4f7d",
        arrow_img=ARROW_DARK_THEME,
    ),
    'light': dict(
        bg="#eef1f7",
        bg_soft="#ffffff",
        card="#ffffff",
        card_hover="#e4eaf4",
        card_hi="#e4eaf4",
        emphasis_bg="#e4eaf4",   # 浅色下比白卡片略深，配合左侧蓝条
        border="#cdd7e5",
        border_hi="#9db2d4",
        text="#1c2536",
        muted="#5f6e8c",
        faint="#8b98b0",         # 占位符：比 muted 浅但仍可读
        accent="#2f6fe0",
        accent_deep="#1d54b8",
        accent_text="#ffffff",
        green="#0fa874",
        green_deep="#0b8a5f",
        green_hover="#12bd85",
        red="#d93a3f",
        red_deep="#b02c31",
        warn="#c77800",
        btn_bg="#f2f5fb",
        btn_border="#bcc9dd",
        btn_hover="#e3eaf6",
        btn_pressed="#d8e1f0",
        btn_disabled_bg="#e9edf4",
        btn_disabled_border="#d4dcea",
        btn_disabled_text="#9aa7bd",
        btn_text="#2a3550",
        scroll_handle="#b9c6dc",
        console_bg="#f6f8fc",
        console_text="#28324a",
        disclaimer_text="#8a5a00",
        indicator_border="#8fa5c8",
        arrow_img=ARROW_LIGHT_THEME,
    ),
}

MONO_STACK = '"Cascadia Mono", "Consolas", "JetBrains Mono", "Courier New", monospace'
UI_STACK = '"Microsoft YaHei UI", "Microsoft YaHei", "PingFang SC", sans-serif'


def palette(theme):
    """取主题调色板（未知主题回退默认）"""
    return PALETTES.get(theme, PALETTES[DEFAULT_THEME])


def build_qss(scale=1.0, theme=DEFAULT_THEME):
    """构建全局样式表，scale 为缩放系数，theme 为 'dark' / 'light'"""
    p = palette(theme)
    dark = theme == 'dark'

    def px(v):
        return round(v * scale)

    def fs(v):
        return round(v * scale)

    # 琥珀强调色在深色底上用亮版、浅色底上用深版；accent_text 是对应的反色文字
    qss = f"""
    /* ============ 基础 ============ */
    QWidget {{
        background: {p['bg']};
        color: {p['text']};
        font-family: {UI_STACK};
        font-size: {fs(FONT_BASE)}px;
        /* 字重只用 normal / bold 两档关键字：Qt5 的 QSS 数值字重是坏的
           —— 数值直接塞进 QFont::setWeight（0~99），700 被截断成 87=Black，
           而雅黑没有 Black 字面，只能拿 Bold 合成加粗，又肥又糊。
           关键字 bold 走的是 QFont::Bold(75)，正好命中雅黑的真实粗体。 */
        font-weight: normal;
    }}
    QWidget:disabled {{ color: {p['btn_disabled_text']}; }}

    QToolTip {{
        background: {p['card_hi']}; color: {p['text']};
        border: 1px solid {p['border_hi']}; border-radius: {px(RADIUS_SM)}px;
        padding: {px(5)}px {px(9)}px;
    }}

    QLabel {{ background: transparent; }}

    /* 文字层级：正文 / 次要 / 辅助说明 / 占位 —— 层级靠颜色与字号，不靠字重 */
    QLabel[tone="muted"]  {{ color: {p['muted']}; }}
    QLabel[tone="warn"]   {{ color: {p['warn']}; font-weight: bold; }}
    QLabel[tone="danger"] {{ color: {p['red']}; font-weight: bold; }}
    QLabel[role="panelHint"]  {{ color: {p['muted']}; font-size: {fs(FONT_SM)}px; }}
    QLabel[role="fieldLabel"] {{ color: {p['text']}; }}
    QLabel[role="help"]       {{ color: {p['muted']}; font-size: {fs(FONT_XS)}px; }}
    QLabel[role="hint2"]      {{ color: {p['faint']}; font-size: {fs(FONT_XS)}px; }}
    /* 关键数字/路径/条数：等宽 + 琥珀，和正文拉开层级 */
    QLabel[role="numeric"] {{
        font-family: {MONO_STACK};
        font-size: {fs(FONT_LG)}px;
        font-weight: bold;
        color: {p['accent']};
    }}
    QLabel[role="metric"] {{
        font-family: {MONO_STACK};
        font-size: {fs(FONT_BASE)}px;
        color: {p['text']};
    }}
    /* 区块小标题：小字号 + 弱色，作为仪器面板的丝印标注（不用粗体，11px 中文加粗会糊） */
    QLabel[role="sectionLabel"] {{
        color: {p['muted']};
        font-size: {fs(FONT_XS)}px;
    }}

    /* ============ 主窗口 / 菜单栏 ============ */
    QMainWindow, QMainWindow > QWidget {{ background: {p['bg']}; }}

    /* 菜单栏右侧的视图控制按钮，紧凑化以匹配菜单行高 */
    QMenuBar QPushButton[variant="ghost"] {{ padding: {px(2)}px {px(9)}px; }}
    QLabel[role="menuHint"] {{ color: {p['faint']}; font-size: {fs(FONT_XS)}px; background: transparent; }}

    #ZoomLabel {{
        font-family: {MONO_STACK};
        font-size: {fs(FONT_XS)}px; color: {p['muted']}; font-weight: bold;
        background: {p['bg_soft']}; border: 1px solid {p['border']};
        border-radius: {px(RADIUS_SM)}px; padding: {px(1)}px {px(8)}px;
    }}
    #HeaderSep    {{ background: {p['border']}; }}

    #Disclaimer {{
        background: {p['card']};
        border: 1px solid {p['border']};
        border-left: {px(3)}px solid {p['warn']};
        border-radius: {px(RADIUS_SM)}px;
        color: {p['disclaimer_text']}; font-size: {fs(FONT_SM)}px;
    }}

    /* ============ 分组卡片 ============ */
    /* 注意：此处不设 font-weight。理由有两条，均已实测：
       1) 标题由 ::title 伪元素绘制，Qt 忽略该伪元素的 font-weight，
          写在这里也到不了标题；
       2) 组框的字体属性会沿继承链渗到组内标签/输入框/复选框，
          造成「卡片内粗、卡片外细」的两套粗细。
       基线字重统一由最外层 QGroupBox 上方的 QWidget 规则兜底。 */
    QGroupBox {{
        background: {p['card']};
        border: 1px solid {p['border']};
        border-radius: {px(RADIUS_MD)}px;
        /* 标题完整落在 margin 区内（不可用负偏移，否则会被相邻控件/视口裁掉上半截） */
        margin-top: {px(22)}px;
        padding: {px(16)}px {px(14)}px {px(14)}px {px(14)}px;
    }}
    /* 标题层级靠字号（15px vs 正文 13px）与位置，不靠字重：
       Qt 的 QGroupBox::title 伪元素忽略 font-weight（实测 normal/bold/700/900
       渲染结果完全一致），写了也是死代码，故不设。 */
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: {px(12)}px; top: 0px;
        padding: 0 {px(6)}px;
        color: {p['text']};
        font-size: {fs(FONT_MD)}px;
    }}
    /* 核心分组：表面更亮 + 左侧琥珀条，建立主次 */
    QGroupBox[emphasis="true"] {{
        background: {p['emphasis_bg']};
        border: 1px solid {p['border_hi']};
        border-left: {px(3)}px solid {p['accent']};
    }}
    QGroupBox[emphasis="true"]::title {{ color: {p['text']}; }}

    /* ============ 输入控件 ============ */
    QLineEdit, QTextEdit, QPlainTextEdit, QDateEdit, QComboBox, QSpinBox {{
        background: {p['bg_soft']};
        border: 1px solid {p['border']};
        border-radius: {px(RADIUS_SM)}px;
        padding: {px(6)}px {px(10)}px;
        color: {p['text']};
        selection-background-color: {p['accent_deep']};
        selection-color: {p['accent_text']};
    }}
    QLineEdit:hover, QTextEdit:hover, QPlainTextEdit:hover, QDateEdit:hover, QComboBox:hover, QSpinBox:hover {{
        border-color: {p['border_hi']};
    }}
    QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QDateEdit:focus, QComboBox:focus, QSpinBox:focus {{
        border: 1px solid {p['accent']};
    }}
    /* 输入格式校验失败（info_input_panel 实时校验）：红框 + tooltip，不阻断输入 */
    QLineEdit[invalid="true"], QLineEdit[invalid="true"]:focus {{
        border: 1px solid {p['red']};
    }}

    QDateEdit::drop-down, QComboBox::drop-down {{
        subcontrol-origin: padding; right: {px(4)}px; width: {px(18)}px;
        border: none; background: transparent;
    }}
    QDateEdit::down-arrow, QComboBox::down-arrow {{
        image: url({p['arrow_img']}); width: {px(12)}px; height: {px(12)}px;
    }}
    QComboBox QAbstractItemView {{
        background: {p['card']}; color: {p['text']};
        border: 1px solid {p['border_hi']};
        border-radius: {px(RADIUS_SM)}px;
        selection-background-color: {p['accent_deep']};
        selection-color: {p['accent_text']};
        outline: none;
        padding: {px(2)}px;
    }}

    QSpinBox::up-button, QSpinBox::down-button {{
        subcontrol-origin: border; width: {px(16)}px;
        border: none; background: transparent;
    }}
    QSpinBox::up-button:hover, QSpinBox::down-button:hover {{ background: {p['card_hover']}; }}
    QSpinBox::up-arrow {{ image: none; border-left: {px(4)}px solid transparent;
        border-right: {px(4)}px solid transparent; border-bottom: {px(5)}px solid {p['muted']}; width: 0; height: 0; }}
    QSpinBox::down-arrow {{ image: none; border-left: {px(4)}px solid transparent;
        border-right: {px(4)}px solid transparent; border-top: {px(5)}px solid {p['muted']}; width: 0; height: 0; }}

    /* ============ 按钮 ============ */
    QPushButton {{
        background: {p['btn_bg']};
        border: 1px solid {p['btn_border']};
        border-radius: {px(RADIUS_SM)}px;
        padding: {px(7)}px {px(16)}px;
        color: {p['btn_text']};
    }}
    QPushButton:hover {{ background: {p['btn_hover']}; border-color: {p['border_hi']}; }}
    QPushButton:pressed {{ background: {p['btn_pressed']}; }}
    QPushButton:disabled {{
        background: {p['btn_disabled_bg']}; border-color: {p['btn_disabled_border']};
        color: {p['btn_disabled_text']};
    }}

    /* 主操作：绿底白字（纯色，不用渐变） */
    QPushButton[variant="primary"] {{
        background: {p['green']};
        border: 1px solid {p['green_deep']};
        color: #ffffff;
        font-weight: bold;
        padding: {px(7)}px {px(18)}px;
    }}
    QPushButton[variant="primary"]:hover {{
        background: {p['green_hover']}; border-color: {p['green_hover']};
    }}
    QPushButton[variant="primary"]:pressed {{
        background: {p['green_deep']}; border-color: {p['green_deep']};
    }}
    QPushButton[variant="primary"]:disabled {{
        background: {p['btn_disabled_bg']}; border-color: {p['btn_disabled_border']};
        color: {p['btn_disabled_text']};
    }}

    QPushButton[variant="danger"] {{
        background: {p['red_deep']};
        border: 1px solid {p['red_deep']};
        color: {p['accent_text']}; font-weight: bold;
    }}
    QPushButton[variant="danger"]:hover {{ background: {p['red']}; border-color: {p['red']}; }}
    QPushButton[variant="danger"]:disabled {{
        background: {p['btn_disabled_bg']}; border-color: {p['btn_disabled_border']};
        color: {p['btn_disabled_text']};
    }}

    QPushButton[variant="ghost"] {{
        background: transparent; border: 1px solid transparent; color: {p['muted']};
        padding: {px(4)}px {px(10)}px;
    }}
    QPushButton[variant="ghost"]:hover {{
        background: {p['card_hover']}; color: {p['text']}; border-color: {p['border']};
    }}
    /* 折叠标题：不加 text-align（QPushButton 不支持，QSS 解析失败会被 Qt 画成红框），
       靠 MaxminSizePolicy 让按钮宽度贴合文字实现左对齐 */
    QPushButton[variant="ghost"][role="disclosure"] {{
        padding: {px(6)}px {px(10)}px;
        color: {p['muted']}; font-size: {fs(FONT_SM)}px; font-weight: bold;
        border: 1px solid transparent;
    }}
    QPushButton[variant="ghost"][role="disclosure"]:hover {{
        color: {p['accent']}; background: {p['card_hover']}; border-color: {p['border']};
    }}
    QPushButton[variant="ghost"]:checked {{
        background: {p['card_hi']}; color: {p['accent']}; border-color: {p['accent_deep']};
    }}

    /* ============ 复选框 / 单选 ============ */
    QCheckBox, QRadioButton {{ background: transparent; spacing: {px(7)}px; }}
    QCheckBox::indicator, QGroupBox::indicator {{
        width: {px(15)}px; height: {px(15)}px;
        border: 1px solid {p['indicator_border']}; border-radius: {px(3)}px;
        background: {p['bg_soft']};
    }}
    QCheckBox::indicator:hover {{ border-color: {p['accent']}; }}
    QCheckBox::indicator:checked {{
        background: {p['accent']}; border-color: {p['accent']};
        image: url({CHECK_IMG});
    }}
    QCheckBox::indicator:disabled {{ border-color: {p['border']}; background: {p['card']}; }}
    QRadioButton::indicator {{
        width: {px(14)}px; height: {px(14)}px;
        border: 1px solid {p['indicator_border']}; border-radius: {px(7)}px;
        background: {p['bg_soft']};
    }}
    QRadioButton::indicator:hover {{ border-color: {p['accent']}; }}
    QRadioButton::indicator:checked {{
        background: qradialgradient(cx:0.5, cy:0.5, radius:0.5,
                    stop:0 {p['accent']}, stop:0.55 {p['accent']}, stop:0.72 {p['bg_soft']}, stop:1 {p['bg_soft']});
        border-color: {p['accent']};
    }}

    /* ============ 提示卡片 ============ */
    #QuickTip {{
        color: {p['muted']}; font-size: {fs(FONT_SM)}px;
        background: {p['bg_soft']}; border: 1px dashed {p['border']};
        border-radius: {px(RADIUS_SM)}px; padding: {px(10)}px;
    }}

    /* ============ 结果控制台 ============ */
    #Console {{
        background: {p['console_bg']};
        border: 1px solid {p['border']};
        border-radius: {px(RADIUS_SM)}px;
        color: {p['console_text']};
        font-family: {MONO_STACK};
        font-size: {fs(FONT_SM)}px;
        selection-background-color: {p['accent_deep']};
        selection-color: {p['accent_text']};
    }}

    /* ============ 进度条（琥珀=进行中，绿=完成，颜色即状态） ============ */
    QProgressBar {{
        background: {p['bg_soft']}; border: 1px solid {p['border']};
        border-radius: {px(RADIUS_SM)}px; height: {px(18)}px;
        text-align: center; color: {p['muted']};
        font-family: {MONO_STACK}; font-size: {fs(FONT_XS)}px;
    }}
    QProgressBar::chunk {{
        border-radius: {px(3)}px;
        background: {p['accent_deep']};
    }}
    QProgressBar[done="true"]::chunk {{
        background: {p['green_deep']};
    }}

    /* ============ 滚动条 ============ */
    QScrollArea {{ background: transparent; border: none; }}
    QScrollArea > QWidget > QWidget {{ background: transparent; }}
    QScrollBar:vertical {{
        background: transparent; width: {px(10)}px; margin: {px(2)}px;
    }}
    QScrollBar::handle:vertical {{
        background: {p['scroll_handle']}; border-radius: {px(3)}px; min-height: {px(30)}px;
    }}
    QScrollBar::handle:vertical:hover {{ background: {p['border_hi']}; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
    QScrollBar:horizontal {{
        background: transparent; height: {px(10)}px; margin: {px(2)}px;
    }}
    QScrollBar::handle:horizontal {{
        background: {p['scroll_handle']}; border-radius: {px(3)}px; min-width: {px(30)}px;
    }}
    QScrollBar::handle:horizontal:hover {{ background: {p['border_hi']}; }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
    QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: transparent; }}

    /* ============ 菜单 ============ */
    QMenuBar {{
        background: {p['bg']}; border-bottom: 1px solid {p['border']};
        color: {p['muted']}; padding: 1px 4px;
    }}
    QMenuBar::item {{ padding: {px(4)}px {px(10)}px; border-radius: {px(RADIUS_SM)}px; background: transparent; }}
    QMenuBar::item:selected {{ background: {p['card_hover']}; color: {p['text']}; }}
    QMenu {{
        background: {p['card']}; color: {p['text']};
        border: 1px solid {p['border_hi']}; border-radius: {px(RADIUS_SM)}px; padding: {px(4)}px;
    }}
    QMenu::item {{ padding: {px(6)}px {px(24)}px {px(6)}px {px(12)}px; border-radius: {px(3)}px; }}
    QMenu::item:selected {{ background: {p['accent_deep']}; color: {p['accent_text']}; }}
    QMenu::separator {{ height: 1px; background: {p['border']}; margin: {px(4)}px {px(8)}px; }}
    QMenu::item:disabled {{ color: {p['faint']}; }}

    /* ============ 状态栏 / 分割线 ============ */
    QStatusBar {{
        background: {p['bg']}; color: {p['faint']};
        border-top: 1px solid {p['border']};
        font-size: {fs(FONT_XS)}px;
    }}
    QStatusBar::item {{ border: none; }}

    QSplitter::handle {{ background: {p['border']}; }}
    QSplitter::handle:horizontal {{ width: {px(3)}px; }}
    QSplitter::handle:vertical {{ height: {px(3)}px; }}
    QSplitter::handle:hover {{ background: {p['accent_deep']}; }}

    /* ============ 日历弹窗 ============ */
    QCalendarWidget QWidget {{ alternate-background-color: {p['card_hover']}; }}
    QCalendarWidget QToolBar {{ background: {p['card']}; border: none; }}
    QCalendarWidget QAbstractItemView {{
        background: {p['bg_soft']}; color: {p['text']};
        selection-background-color: {p['accent_deep']}; selection-color: {p['accent_text']};
    }}
    """
    return qss
