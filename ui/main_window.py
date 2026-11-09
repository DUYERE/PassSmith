"""主窗口 - 头部栏 + 面板组装 + 全屏/缩放 + 设置记忆"""

import os

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QSplitter, QAction, QApplication, QMessageBox,
    QShortcut, QFrame, QDialog,
)
from PyQt5.QtCore import Qt, QTimer, QSettings, QSize
from PyQt5.QtGui import QIcon, QKeySequence

from ui.info_input_panel import InfoInputPanel
from ui.rule_config_panel import RuleConfigPanel
from ui.output_panel import OutputPanel
from ui.tools_dialogs import BatchDialog, MergeDialog, TemplateDialog, HistoryDialog
from ui.theme import APP_ICON, ZOOM_STEPS, DEFAULT_ZOOM, DEFAULT_THEME, THEMES, build_qss
from core.combiner import PasswordGenerator

ORG_NAME = "PassSmith"
APP_NAME = "PassSmith"
DEFAULT_SIZE = (1280, 860)
# 分栏默认比例（上下：信息区/输出区；左右：信息/规则）
# 上下 50/50：结果预览是核心产出区，不能被输入区挤压
V_SPLIT_RATIO = [0.58, 0.42]
H_SPLIT_RATIO = [0.60, 0.40]
# 历史版本默认值：老用户未拖动过分栏时迁移到新比例
OLD_V_DEFAULT = [0.56, 0.44]


class MainWindow(QMainWindow):
    """主窗口"""

    def __init__(self):
        super().__init__()
        self.generator = PasswordGenerator()
        self.zoom = DEFAULT_ZOOM
        self.theme = DEFAULT_THEME
        self._settings = QSettings(ORG_NAME, APP_NAME)
        self._pre_fullscreen_state = None
        self._placement_checked = False
        self._v_ratio = list(V_SPLIT_RATIO)
        self._h_ratio = list(H_SPLIT_RATIO)

        self._init_ui()
        self._init_menus()
        self._init_shortcuts()
        self._connect_signals()
        self._restore_settings()

    # ------------------------------------------------------------------ UI

    def _init_ui(self):
        self.setWindowTitle("PassSmith — 社工密码字典生成器")
        if APP_ICON and os.path.exists(APP_ICON):
            self.setWindowIcon(QIcon(APP_ICON))
        self.setMinimumSize(760, 520)
        self.resize(*DEFAULT_SIZE)

        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        root_layout.addWidget(self._build_disclaimer())
        self.body_splitter = self._build_body()
        root_layout.addWidget(self.body_splitter, 1)

        self.statusBar().showMessage("就绪 · 输入目标信息后点击「开始生成」")

    def _app_icon_pixmap(self, base_size):
        """取平滑缩放的应用图标位图（用于关于对话框等）"""
        if not APP_ICON or not os.path.exists(APP_ICON):
            return None
        icon = self.windowIcon()
        dpr = self.devicePixelRatioF() if hasattr(self, 'devicePixelRatioF') else 1.0
        target = max(1, round(base_size * self.zoom * dpr))
        pm = icon.pixmap(target, target)
        if pm.isNull():
            return None
        if pm.width() != target:
            pm = pm.scaled(target, target, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        pm.setDevicePixelRatio(dpr)
        return pm

    def _build_menubar_controls(self):
        """菜单栏右侧角落的视图控制：缩小 / 百分比 / 放大 | 重置 | 主题 | 全屏 | 署名"""
        corner = QWidget()
        layout = QHBoxLayout(corner)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(6)

        self.zoom_out_btn = self._header_button("－", "缩小界面 (Ctrl+-)")
        self.zoom_in_btn = self._header_button("＋", "放大界面 (Ctrl+=)")
        self.zoom_label = QLabel(f"{int(self.zoom * 100)}%")
        self.zoom_label.setObjectName("ZoomLabel")
        self.zoom_label.setAlignment(Qt.AlignCenter)
        self.zoom_reset_btn = self._header_button("重置", "恢复默认缩放 (Ctrl+0)")
        self.theme_btn = self._header_button("浅色", "切换浅色 / 深色主题")
        # 两种状态等长文案：QMenuBar 不会为角落控件按新文本重算宽度，不等长会被裁切
        self.fullscreen_btn = self._header_button("⛶ 进入全屏", "进入全屏 (F11，Esc 退出)")

        self.zoom_out_btn.clicked.connect(lambda: self._change_zoom(-1))
        self.zoom_in_btn.clicked.connect(lambda: self._change_zoom(1))
        self.zoom_reset_btn.clicked.connect(self._reset_zoom)
        self.theme_btn.clicked.connect(self.toggle_theme)
        self.fullscreen_btn.clicked.connect(self.toggle_fullscreen)

        layout.addWidget(self.zoom_out_btn)
        layout.addWidget(self.zoom_label)
        layout.addWidget(self.zoom_in_btn)
        layout.addWidget(self._header_separator())
        layout.addWidget(self.zoom_reset_btn)
        layout.addWidget(self._header_separator())
        layout.addWidget(self.theme_btn)
        layout.addWidget(self._header_separator())
        layout.addWidget(self.fullscreen_btn)

        signature = QLabel("by 止戈")
        signature.setProperty("role", "menuHint")
        layout.addSpacing(4)
        layout.addWidget(signature)
        return corner

    @staticmethod
    def _header_button(text, tooltip):
        btn = QPushButton(text)
        btn.setProperty("variant", "ghost")
        btn.setCursor(Qt.PointingHandCursor)
        btn.setToolTip(tooltip)
        return btn

    @staticmethod
    def _header_separator():
        line = QFrame()
        line.setObjectName("HeaderSep")
        line.setFixedSize(1, 18)
        return line

    def _build_disclaimer(self):
        disclaimer = QLabel(
            "⚠ 声明：本工具仅供授权安全测试使用，禁止用于任何非法用途。"
            "使用本工具即表示您已获得目标系统所有者的合法授权。"
        )
        disclaimer.setObjectName("Disclaimer")
        disclaimer.setWordWrap(True)
        disclaimer.setContentsMargins(12, 6, 12, 6)
        wrapper = QWidget()
        wrap_layout = QVBoxLayout(wrapper)
        wrap_layout.setContentsMargins(12, 8, 12, 0)
        wrap_layout.addWidget(disclaimer)
        return wrapper

    def _build_body(self):
        """左右分割（信息/规则）+ 上下分割（输出）"""
        splitter = QSplitter(Qt.Vertical)
        splitter.setChildrenCollapsible(False)
        splitter.setContentsMargins(10, 8, 10, 8)

        top_widget = QWidget()
        top_layout = QHBoxLayout(top_widget)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(8)

        self.info_panel = InfoInputPanel()
        self.rule_panel = RuleConfigPanel()

        self.top_splitter = QSplitter(Qt.Horizontal)
        self.top_splitter.setChildrenCollapsible(False)
        self.top_splitter.addWidget(self.info_panel)
        self.top_splitter.addWidget(self.rule_panel)
        self.top_splitter.setStretchFactor(0, 3)
        self.top_splitter.setStretchFactor(1, 2)
        self.top_splitter.setSizes([620, 400])
        top_layout.addWidget(self.top_splitter)

        self.output_panel = OutputPanel(generator=self.generator)
        # 生成时实时读取最新信息与规则（修复此前数据源未接线导致无法生成的问题）
        self.output_panel.set_providers(
            self.info_panel.get_info_data,
            self.rule_panel.get_rules_config,
        )

        splitter.addWidget(top_widget)
        splitter.addWidget(self.output_panel)
        # 上部 6 : 下部 4——左侧有 5 个分组共 9 行输入，比例 5:4 时「社交关系」
        # 第二行会被裁掉；输出区保底高度由预览控件 minHeight + 导出两行决定，缩一点仍够用
        splitter.setStretchFactor(0, 6)
        splitter.setStretchFactor(1, 4)
        self._apply_splitter_ratios(splitter)

        # 用户拖动分栏时更新比例记忆
        splitter.splitterMoved.connect(lambda _p, _i: self._store_ratio(self.body_splitter, self._v_ratio))
        self.top_splitter.splitterMoved.connect(lambda _p, _i: self._store_ratio(self.top_splitter, self._h_ratio))

        return splitter

    def _apply_splitter_ratios(self, splitter):
        """按比例设置上下分栏尺寸"""
        total = sum(splitter.sizes())
        if total > 100:
            splitter.setSizes([round(total * r) for r in self._v_ratio])

    @staticmethod
    def _store_ratio(splitter, ratio_list):
        sizes = splitter.sizes()
        total = sum(sizes)
        if total > 0:
            ratio_list[:] = [s / total for s in sizes]

    def _init_menus(self):
        menu_bar = self.menuBar()

        view_menu = menu_bar.addMenu("视图(&V)")

        self.fullscreen_action = QAction("全屏模式", self)
        self.fullscreen_action.setCheckable(True)
        self.fullscreen_action.setShortcut(QKeySequence(Qt.Key_F11))
        self.fullscreen_action.triggered.connect(self.toggle_fullscreen)
        view_menu.addAction(self.fullscreen_action)
        view_menu.addSeparator()

        zoom_in_action = QAction("放大", self)
        zoom_in_action.setShortcuts([QKeySequence("Ctrl+="), QKeySequence("Ctrl++")])
        zoom_in_action.triggered.connect(lambda: self._change_zoom(1))
        view_menu.addAction(zoom_in_action)

        zoom_out_action = QAction("缩小", self)
        zoom_out_action.setShortcut(QKeySequence("Ctrl+-"))
        zoom_out_action.triggered.connect(lambda: self._change_zoom(-1))
        view_menu.addAction(zoom_out_action)

        zoom_reset_action = QAction("重置缩放", self)
        zoom_reset_action.setShortcut(QKeySequence("Ctrl+0"))
        zoom_reset_action.triggered.connect(self._reset_zoom)
        view_menu.addAction(zoom_reset_action)
        view_menu.addSeparator()

        theme_action = QAction("切换浅色 / 深色主题", self)
        theme_action.triggered.connect(self.toggle_theme)
        view_menu.addAction(theme_action)

        tools_menu = menu_bar.addMenu("工具(&T)")

        batch_action = QAction("批量生成（CSV 多目标）…", self)
        batch_action.triggered.connect(self._open_batch)
        tools_menu.addAction(batch_action)

        merge_action = QAction("字典合并 / 差集（排除已试）…", self)
        merge_action.triggered.connect(self._open_merge)
        tools_menu.addAction(merge_action)
        tools_menu.addSeparator()

        template_action = QAction("配置模板…", self)
        template_action.triggered.connect(self._open_templates)
        tools_menu.addAction(template_action)

        history_action = QAction("生成历史…", self)
        history_action.triggered.connect(self._open_history)
        tools_menu.addAction(history_action)

        help_menu = menu_bar.addMenu("帮助(&H)")
        about_action = QAction("关于 PassSmith", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

        # 视图控制按钮放到菜单栏右侧，与"视图/帮助"同一行
        menu_bar.setCornerWidget(self._build_menubar_controls(), Qt.TopRightCorner)

    def _init_shortcuts(self):
        # Esc 退出全屏
        esc = QShortcut(QKeySequence(Qt.Key_Escape), self)
        esc.activated.connect(self._exit_fullscreen)

        # Ctrl+S 导出 TXT（与浏览器/编辑器的保存习惯一致）
        save = QShortcut(QKeySequence("Ctrl+S"), self)
        save.activated.connect(self.output_panel._export_txt)

        # Ctrl+Shift+C 复制全部结果
        copy = QShortcut(QKeySequence("Ctrl+Shift+C"), self)
        copy.activated.connect(self.output_panel._copy_all)

    # -------------------------------------------------------------- 全屏/缩放

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self._exit_fullscreen()
        else:
            self._pre_fullscreen_state = self.windowState()
            self.showFullScreen()
            self._sync_fullscreen_ui(True)

    def _exit_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
            if self._pre_fullscreen_state is not None:
                self.setWindowState(self._pre_fullscreen_state)
            self._sync_fullscreen_ui(False)

    def _sync_fullscreen_ui(self, fullscreen):
        self.fullscreen_action.setChecked(fullscreen)
        self.fullscreen_btn.setText("⛶ 退出全屏" if fullscreen else "⛶ 进入全屏")
        self.fullscreen_btn.setToolTip("退出全屏 (Esc)" if fullscreen else "进入全屏 (F11)")
        self.menuBar().updateGeometry()

    def wheelEvent(self, event):
        """Ctrl + 滚轮 缩放界面"""
        if event.modifiers() & Qt.ControlModifier:
            delta = event.angleDelta().y()
            if delta:
                self._change_zoom(1 if delta > 0 else -1)
                event.accept()
                return
        super().wheelEvent(event)

    def resizeEvent(self, event):
        """窗口尺寸变化时分栏按比例跟随（最大化/还原后内容不再被裁切）"""
        super().resizeEvent(event)
        if getattr(self, 'body_splitter', None) is None:
            return
        # 布局要在事件循环下一拍才把新尺寸分给分栏，推迟到那时再按比例重分布
        QTimer.singleShot(0, self._sync_splitter_ratios)

    def _sync_splitter_ratios(self):
        for splitter, ratios in ((self.body_splitter, self._v_ratio),
                                 (self.top_splitter, self._h_ratio)):
            total = sum(splitter.sizes())
            if total > 100:
                splitter.setSizes([round(total * r) for r in ratios])

    def _change_zoom(self, direction):
        try:
            idx = ZOOM_STEPS.index(self.zoom)
        except ValueError:
            idx = ZOOM_STEPS.index(DEFAULT_ZOOM)
        new_idx = max(0, min(len(ZOOM_STEPS) - 1, idx + direction))
        if ZOOM_STEPS[new_idx] != self.zoom:
            self._apply_zoom(ZOOM_STEPS[new_idx])

    def _reset_zoom(self):
        self._apply_zoom(DEFAULT_ZOOM)

    def _apply_zoom(self, scale):
        """应用整体缩放：重建样式表 + 同步头部装饰 + 各面板固定高度"""
        self.zoom = scale
        QApplication.instance().setStyleSheet(build_qss(scale, self.theme))

        self._sync_zoom_buttons()
        for panel in (self.info_panel, self.rule_panel, self.output_panel):
            apply_zoom = getattr(panel, 'apply_zoom', None)
            if apply_zoom:
                apply_zoom(scale)

        # 已打开的工具对话框同步缩放（正常流程下模态期间改不了缩放，属防御性处理）
        for dialog in self.findChildren(QDialog):
            apply_zoom = getattr(dialog, 'apply_zoom', None)
            if apply_zoom and dialog.isVisible():
                apply_zoom(scale)

        self._settings.setValue("ui/zoom", scale)
        self.statusBar().showMessage(f"界面缩放: {int(scale * 100)}%", 2000)

    # ------------------------------------------------------------------ 主题

    def toggle_theme(self):
        self._apply_theme('light' if self.theme == 'dark' else 'dark')

    def _apply_theme(self, theme, save=True):
        """切换深色/浅色主题（重建样式表）"""
        if theme not in THEMES:
            theme = DEFAULT_THEME
        self.theme = theme
        QApplication.instance().setStyleSheet(build_qss(self.zoom, theme))

        self.theme_btn.setText("深色" if theme == 'light' else "浅色")
        self.theme_btn.setToolTip("切换到深色主题" if theme == 'light' else "切换到浅色主题")
        if save:
            self._settings.setValue("ui/theme", theme)
            self.statusBar().showMessage("已切换到浅色主题" if theme == 'light' else "已切换到深色主题", 2000)

    def _sync_zoom_buttons(self):
        """更新缩放按钮态与百分比标签"""
        self.zoom_in_btn.setEnabled(self.zoom < ZOOM_STEPS[-1])
        self.zoom_out_btn.setEnabled(self.zoom > ZOOM_STEPS[0])
        self.zoom_reset_btn.setEnabled(abs(self.zoom - DEFAULT_ZOOM) > 1e-6)
        self.zoom_label.setText(f"{int(round(self.zoom * 100))}%")

    # ------------------------------------------------------------------ 信号

    def _connect_signals(self):
        # 规则配置变更（含弱口令、筛选、长度等全部控件）
        self.rule_panel.config_changed.connect(self._schedule_estimate)

        # 信息输入：文本 / 日期 / 启用复选框
        for widget in self.info_panel.fields.values():
            if hasattr(widget, 'textChanged'):
                widget.textChanged.connect(self._schedule_estimate)
            if hasattr(widget, 'dateChanged'):
                widget.dateChanged.connect(self._schedule_estimate)
        for check in self.info_panel.date_checks.values():
            check.toggled.connect(self._schedule_estimate)

        # 防抖：输入变化 250ms 后再重算预估，避免逐键卡顿
        self._estimate_timer = QTimer(self)
        self._estimate_timer.setSingleShot(True)
        self._estimate_timer.setInterval(250)
        self._estimate_timer.timeout.connect(self._update_estimate)

        # 输出面板 -> 状态栏
        self.output_panel.status_changed.connect(
            lambda msg: self.statusBar().showMessage(msg, 5000)
        )

    # ------------------------------------------------------------------ 预估

    def _schedule_estimate(self):
        self._estimate_timer.start()

    def _update_estimate(self):
        info_data = self.info_panel.get_info_data()
        rules_config = self.rule_panel.get_rules_config()
        valid_data = {k: v for k, v in info_data.items() if v}

        if not valid_data:
            # 无个人信息时：若「姓名+弱口令」开启，预估值即纯弱口令条数（需过完长度筛选）
            try:
                estimated, _ = self.generator.estimate_count(valid_data, rules_config, detail=True)
            except Exception:
                estimated = 0
            self.output_panel.update_estimate(estimated)
            if estimated > 0:
                self.output_panel.estimate_unit.setText("条（仅纯弱口令）")
            return

        try:
            estimated, exact = self.generator.estimate_count(valid_data, rules_config, detail=True)
            # 非精确预估（大字典走算术估算）才需要提示「实际会减少」
            self.output_panel.update_estimate(estimated, not exact)
        except Exception:
            self.output_panel.update_estimate(0)

    # ------------------------------------------------------------------ 工具

    def _open_batch(self):
        """批量模式：CSV 多目标，每个目标一个独立字典文件"""
        self._show_dialog(BatchDialog(self.rule_panel.get_rules_config, self))

    def _open_merge(self):
        """字典合并/去重"""
        self._show_dialog(MergeDialog(self))

    def _open_templates(self):
        """配置模板：保存/加载整份信息与规则"""
        self._show_dialog(TemplateDialog(
            self.info_panel.get_info_data,
            self.rule_panel.get_rules_config,
            self.info_panel.set_info_data,
            self.rule_panel.set_rules_config,
            self,
        ))

    def _open_history(self):
        """生成历史"""
        self._show_dialog(HistoryDialog(self))

    def _show_dialog(self, dialog):
        """统一打开工具对话框：先应用当前缩放再模态显示（QSS 字号由全局样式表负责）"""
        apply_zoom = getattr(dialog, 'apply_zoom', None)
        if apply_zoom:
            apply_zoom(self.zoom)
        # 高缩放档位下对话框会超出屏幕，钳制到可用区域
        avail = QApplication.primaryScreen().availableGeometry()
        max_w, max_h = avail.width() - 60, avail.height() - 60
        if dialog.width() > max_w or dialog.height() > max_h:
            dialog.resize(min(dialog.width(), max_w), min(dialog.height(), max_h))
        dialog.exec_()

    # ------------------------------------------------------------------ 关于

    def _show_about(self):
        msg = QMessageBox(self)
        msg.setWindowTitle("关于 PassSmith")
        pm = self._app_icon_pixmap(64)
        if pm is not None:
            msg.setIconPixmap(pm)
        msg.setText(
            "<b>PassSmith 社工密码字典生成器</b><br><br>"
            "基于目标个人信息智能生成高命中率密码字典，"
            "用于授权渗透测试与安全评估。<br><br>"
            "<b>快捷键</b><br>"
            "F11 — 全屏切换（Esc 退出）<br>"
            "Ctrl+S — 导出 TXT<br>"
            "Ctrl+Shift+C — 复制全部结果<br>"
            "Ctrl+= / Ctrl+- / Ctrl+0 — 放大 / 缩小 / 重置界面<br>"
            "Ctrl+鼠标滚轮 — 快速缩放<br><br>"
            "by 止戈"
        )
        msg.exec_()

    # ------------------------------------------------------------------ 设置

    def _restore_settings(self):
        geo = self._settings.value("ui/geometry")
        restored = False
        if geo is not None:
            restored = self.restoreGeometry(geo)
        if not restored:
            # 首次启动：默认尺寸并居中（显示后的落位校验见 _ensure_on_screen）
            self.resize(*DEFAULT_SIZE)
            self._center_on_screen()

        saved_zoom = self._settings.value("ui/zoom", DEFAULT_ZOOM, type=float)
        self._apply_zoom(saved_zoom if saved_zoom in ZOOM_STEPS else DEFAULT_ZOOM)

        theme = self._settings.value("ui/theme", DEFAULT_THEME)
        self._apply_theme(theme, save=False)

        v = self._settings.value("ui/split_ratio_v", None)
        if isinstance(v, list) and len(v) == 2:
            try:
                self._v_ratio = [float(v[0]), float(v[1])]
            except (TypeError, ValueError):
                pass
        # 老用户保存的正是旧默认比例时，跟随新默认（预览区加高），拖动过的保留
        if self._v_ratio == OLD_V_DEFAULT:
            self._v_ratio = list(V_SPLIT_RATIO)
        h = self._settings.value("ui/split_ratio_h", None)
        if isinstance(h, list) and len(h) == 2:
            try:
                self._h_ratio = [float(h[0]), float(h[1])]
            except (TypeError, ValueError):
                pass
        self._apply_splitter_ratios(self.body_splitter)

        self._update_estimate()

    def showEvent(self, event):
        super().showEvent(event)
        if not self._placement_checked:
            # 窗口管理器落位后校验（show 之前 frameGeometry 不含标题栏边框，无法准确判断）
            self._placement_checked = True
            QTimer.singleShot(0, self._ensure_on_screen)

    def _ensure_on_screen(self):
        """把标题栏被屏幕裁掉的窗口拉回可见区域（修复恢复历史几何后图标/标题栏不可见）"""
        if self.isFullScreen() or self.isMaximized():
            return
        avail = self.screen().availableGeometry()
        frame = self.frameGeometry()
        x = min(max(frame.left(), avail.left()), avail.right() - 120)
        y = min(max(frame.top(), avail.top()), avail.bottom() - 120)
        if x != frame.left() or y != frame.top():
            self.move(x, y)

    def _center_on_screen(self):
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(
            screen.x() + (screen.width() - self.width()) // 2,
            screen.y() + (screen.height() - self.height()) // 2,
        )

    def closeEvent(self, event):
        if not self.isFullScreen():
            self._settings.setValue("ui/geometry", self.saveGeometry())
        self._settings.setValue("ui/zoom", self.zoom)
        # 分栏按比例记忆，窗口尺寸变化时依然成立
        self._store_ratio(self.body_splitter, self._v_ratio)
        self._store_ratio(self.top_splitter, self._h_ratio)
        self._settings.setValue("ui/split_ratio_v", self._v_ratio)
        self._settings.setValue("ui/split_ratio_h", self._h_ratio)
        super().closeEvent(event)
