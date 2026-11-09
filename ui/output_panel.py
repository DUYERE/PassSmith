"""输出控制面板 - 生成控制、结果预览、导出功能"""

import os
import time

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QPushButton,
    QPlainTextEdit, QProgressBar, QComboBox, QCheckBox, QSpinBox,
    QFileDialog, QMessageBox, QScrollArea, QApplication
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSettings
from PyQt5.QtGui import QTextCursor
from utils.exporter import export_txt, export_csv

LAST_DIR_KEY = "export/last_dir"
PREVIEW_LINES = 100
BATCH_SIZE = 200


class GenerateThread(QThread):
    """后台生成线程"""
    progress = pyqtSignal(int, int)     # current, estimated
    batch_ready = pyqtSignal(list)      # 批量密码
    finished_count = pyqtSignal(int)    # 最终数量
    stopped = pyqtSignal(int)           # 用户中断：只上报已生成条数，不走「完成」流程
    error = pyqtSignal(str)

    def __init__(self, generator, info_data, rules_config):
        super().__init__()
        self.generator = generator
        self.info_data = info_data
        self.rules_config = rules_config
        self._running = True

    def run(self):
        try:
            estimated = self.generator.estimate_count(self.info_data, self.rules_config)
            count = 0
            batch = []

            passwords = self.generator.generate(self.info_data, self.rules_config)
            for pwd in passwords:
                if not self._running:
                    break

                count += 1
                batch.append(pwd)

                # 每批 BATCH_SIZE 条发送一次，避免信号过于频繁
                if len(batch) >= BATCH_SIZE:
                    self.batch_ready.emit(batch[:])
                    batch.clear()
                    self.progress.emit(count, estimated)

            if batch:
                self.batch_ready.emit(batch[:])

            # 中断与完成必须分开：走 finished_count 会把进度条改成「完成」，
            # 并触发 _record_history 写一条用户并没有真正生成的记录
            if self._running:
                self.progress.emit(count, count)
                self.finished_count.emit(count)
            else:
                self.stopped.emit(count)

        except Exception as e:
            self.error.emit(str(e))

    def stop(self):
        self._running = False


class OutputPanel(QWidget):
    """输出控制面板"""

    status_changed = pyqtSignal(str)  # 发给主窗口状态栏的临时消息

    def __init__(self, generator=None, parent=None):
        super().__init__(parent)
        from core.combiner import PasswordGenerator
        self.generator = generator or PasswordGenerator()
        self.all_passwords = []
        self.generate_thread = None
        self._info_provider = None
        self._rules_provider = None
        self._settings = QSettings("PassSmith", "PassSmith")
        # 显式最小高度：分栏按比例分配时允许压缩，内容不足时出滚动条而非裁切
        self.setMinimumHeight(200)

        # 内容包进滚动容器：面板空间不足时滚动查看，避免控件互相覆盖
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 2, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        content = QWidget()
        self._build_content(content)

        scroll.setWidget(content)
        outer_layout.addWidget(scroll)

    def _build_content(self, host):
        main_layout = QVBoxLayout(host)
        main_layout.setSpacing(4)
        main_layout.setContentsMargins(0, 0, 2, 0)

        # ===== 生成控制（紧凑：按钮行内联预估，进度条即状态） =====
        # 注意：QGroupBox 的 QSS 已带 12px padding，组内 layout 必须
        # 清零 Qt 默认的 9px 边距，否则双重叠加每组虚高 18px
        ctrl_group = QGroupBox("生成控制")
        ctrl_layout = QVBoxLayout()
        ctrl_layout.setContentsMargins(0, 0, 0, 0)
        ctrl_layout.setSpacing(6)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(6)
        self.generate_btn = self._button("开始生成", "primary", "开始生成密码字典")
        self.generate_btn.clicked.connect(self._on_generate)
        self.stop_btn = self._button("停止", "danger", "停止生成")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._on_stop)
        self.clear_btn = self._button("清空结果", None, "清空当前结果")
        self.clear_btn.clicked.connect(self._on_clear)
        self.copy_btn = self._button("复制全部", None, "复制全部结果到剪贴板（在线爆破直接粘贴到 Burp/自定义脚本）")
        self.copy_btn.setEnabled(False)
        self.copy_btn.clicked.connect(self._copy_all)

        btn_layout.addWidget(self.generate_btn)
        btn_layout.addWidget(self.stop_btn)
        btn_layout.addWidget(self.clear_btn)
        btn_layout.addWidget(self.copy_btn)
        btn_layout.addStretch()
        # 预估读数：小字标签 + 大号等宽数字 + 单位，像仪器面板上的读数
        est_row = QHBoxLayout()
        est_row.setContentsMargins(0, 0, 0, 0)
        est_row.setSpacing(6)
        est_caption = QLabel("预估值")
        est_caption.setProperty("role", "sectionLabel")
        est_row.addWidget(est_caption)
        self.estimate_label = QLabel("—")
        self.estimate_label.setProperty("role", "numeric")
        self.estimate_label.setProperty("tone", "muted")
        est_row.addWidget(self.estimate_label)
        self.estimate_unit = QLabel("条")
        self.estimate_unit.setProperty("role", "panelHint")
        est_row.addWidget(self.estimate_unit)
        btn_layout.addLayout(est_row)
        ctrl_layout.addLayout(btn_layout)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("待机")
        ctrl_layout.addWidget(self.progress_bar)

        ctrl_group.setLayout(ctrl_layout)
        main_layout.addWidget(ctrl_group)

        # ===== 结果预览 =====
        preview_group = QGroupBox(f"结果预览（前{PREVIEW_LINES}条）")
        preview_layout = QVBoxLayout()
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.setSpacing(0)

        # QPlainTextEdit：纯文本追加，密码中的 < > & 等字符不会被当作 HTML 吞掉
        self.preview_text = QPlainTextEdit()
        self.preview_text.setReadOnly(True)
        # 预览是核心产出区：保底高度保证可读。下限取值以「用户把输出区拖到最矮
        # （~305px）时导出组仍完整可见」为约束，多余空间由 stretch 分给预览
        self.preview_text.setMinimumHeight(88)
        self.preview_text.setObjectName("Console")
        self.preview_text.setPlaceholderText(
            "生成结果将显示在这里\n"
            "\n"
            "左侧填信息  →  右侧确认规则  →  点击「开始生成」\n"
            "不填信息也能生成，只输出纯弱口令")
        preview_layout.addWidget(self.preview_text)

        preview_group.setLayout(preview_layout)
        main_layout.addWidget(preview_group, 1)

        # ===== 导出 =====
        # 两行：上排「导出动作 + 编码」，下排「文件切分方式」。
        # 原来 6 个控件挤一行，「编码 / 拆分 / 分档」三种语义混在一起扫读困难。
        export_group = QGroupBox("导出")
        export_outer = QVBoxLayout()
        export_outer.setContentsMargins(0, 0, 0, 0)
        export_outer.setSpacing(8)

        row_action = QHBoxLayout()
        row_action.setContentsMargins(0, 0, 0, 0)
        self.export_txt_btn = self._button("导出 TXT", None, "导出为TXT文件（面向爆破工具，不做任何转义）")
        self.export_txt_btn.setEnabled(False)
        self.export_txt_btn.clicked.connect(self._export_txt)
        self.export_csv_btn = self._button("导出 CSV", None, "导出为CSV文件（面向 Excel 查看）")
        self.export_csv_btn.setEnabled(False)
        self.export_csv_btn.clicked.connect(self._export_csv)

        row_action.addWidget(self.export_txt_btn)
        row_action.addWidget(self.export_csv_btn)
        row_action.addStretch()
        row_action.addWidget(QLabel("编码:"))
        self.encoding_combo = QComboBox()
        self.encoding_combo.addItems(["UTF-8", "GBK"])
        row_action.addWidget(self.encoding_combo)
        export_outer.addLayout(row_action)

        row_mode = QHBoxLayout()
        row_mode.setContentsMargins(0, 0, 0, 0)
        self.split_check = QCheckBox("拆分文件, 每")
        row_mode.addWidget(self.split_check)

        self.split_spin = QSpinBox()
        self.split_spin.setRange(1000, 1000000)
        self.split_spin.setValue(10000)
        self.split_spin.setSingleStep(1000)
        self.split_spin.setGroupSeparatorShown(True)
        row_mode.addWidget(self.split_spin)
        row_mode.addWidget(QLabel("条"))

        row_mode.addSpacing(16)
        # 分档导出：在线爆破先试 Top100 / Top1000，再全量，省去手工切分
        self.tier_check = QCheckBox("分档导出 Top100/1000")
        self.tier_check.setToolTip("同时生成 _top100.txt、_top1000.txt 与全量文件（与「拆分文件」互斥）")
        row_mode.addWidget(self.tier_check)
        row_mode.addStretch()

        # 两种导出模式互斥，避免同时勾选产生命名冲突
        self.tier_check.toggled.connect(lambda on: self.split_check.setChecked(False) if on else None)
        self.split_check.toggled.connect(lambda on: self.tier_check.setChecked(False) if on else None)
        export_outer.addLayout(row_mode)

        export_group.setLayout(export_outer)
        main_layout.addWidget(export_group)

    @staticmethod
    def _button(text, variant, tooltip):
        btn = QPushButton(text)
        if variant:
            btn.setProperty("variant", variant)
        btn.setMinimumHeight(30)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setToolTip(tooltip)
        return btn

    # ---------------------------------------------------------------- 数据源

    def set_providers(self, info_provider, rules_provider):
        """绑定信息/规则的实时读取函数（生成时取最新值）"""
        self._info_provider = info_provider
        self._rules_provider = rules_provider

    def update_estimate(self, count, approximate=False):
        """更新预估值：颜色只作阈值信号——常态中性，10万橙色提醒，50万红色警告

        approximate=True 表示大字典走了算术估算（未计入筛选与去重），需标注提示。
        """
        label = self.estimate_label
        unit = self.estimate_unit
        suffix = "（估算，实际略少）" if approximate else ""
        if count <= 0:
            label.setText("—")
            unit.setText("条（请输入信息）")
            label.setProperty("tone", "muted")
        elif count > 500000:
            label.setText(f"{count:,}")
            unit.setText(f"条{suffix} · 数量过大，建议降低组合深度")
            label.setProperty("tone", "danger")
        elif count > 100000:
            label.setText(f"{count:,}")
            unit.setText(f"条{suffix} · 生成可能较慢")
            label.setProperty("tone", "warn")
        else:
            label.setText(f"{count:,}")
            unit.setText(f"条{suffix}")
            label.setProperty("tone", "muted")
        for w in (label, unit):
            w.style().unpolish(w)
            w.style().polish(w)

    def apply_zoom(self, scale):
        """缩放支持：按钮基准高度等比缩放"""
        for btn in (self.generate_btn, self.stop_btn, self.clear_btn,
                    self.export_txt_btn, self.export_csv_btn):
            btn.setMinimumHeight(round(30 * scale))

    # ---------------------------------------------------------------- 生成

    def _collect_inputs(self):
        info_data = self._info_provider() if callable(self._info_provider) else {}
        rules_config = self._rules_provider() if callable(self._rules_provider) else {}
        return info_data, rules_config

    def _on_generate(self):
        """开始生成"""
        info_data, rules_config = self._collect_inputs()

        if not info_data or not any(info_data.values()):
            # 无个人信息时仍可导出纯弱口令字典——0 级通道不依赖任何个人信息
            weak_count = len(rules_config.get('weak_passwords') or [])
            if not rules_config.get('quick_rules', {}).get('name_weak', True) or weak_count == 0:
                QMessageBox.warning(self, "提示", "请至少输入一项有效信息！")
                return
            reply = QMessageBox.question(
                self, "仅生成纯弱口令？",
                f"未填写任何个人信息，将只输出纯弱口令列表中的词"
                f"（已按长度 {rules_config.get('min_len', 5)}-{rules_config.get('max_len', 20)} 筛选），"
                "不含姓名/生日等衍生组合。\n\n是否继续？",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes,
            )
            if reply != QMessageBox.Yes:
                return

        # 预估数量过大时确认
        estimated = self.generator.estimate_count(info_data, rules_config)
        if estimated > 500000:
            reply = QMessageBox.warning(
                self, "数量警告",
                f"预计生成超过 {estimated:,} 条密码，可能导致内存占用过大。\n"
                f"建议减少组合深度或关闭部分规则。\n\n是否继续？",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.No:
                return

        self.all_passwords = []
        self.preview_text.clear()
        self._set_progress_done(False)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("生成中…")

        self.generate_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.export_txt_btn.setEnabled(False)
        self.export_csv_btn.setEnabled(False)

        self._started_at = time.monotonic()

        self.generate_thread = GenerateThread(self.generator, info_data, rules_config)
        self.generate_thread.batch_ready.connect(self._on_batch_ready)
        self.generate_thread.progress.connect(self._on_progress)
        self.generate_thread.finished_count.connect(self._on_finished)
        self.generate_thread.stopped.connect(self._on_stopped)
        self.generate_thread.error.connect(self._on_error)
        self.generate_thread.start()
        self.status_changed.emit("开始生成密码字典…")

    def _on_stop(self):
        """停止生成"""
        thread = self.generate_thread
        if thread and thread.isRunning():
            thread.stop()
            thread.wait(3000)

        # 按钮立即复位；进度文字与计数由 stopped 信号补齐
        # （最后一批可能还在队列里，此处读 all_passwords 会偏少）
        self.generate_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self._update_export_buttons()

    def _on_stopped(self, count):
        """用户中断后的收尾：不写历史、不标记完成"""
        if self.sender() is not self.generate_thread:
            return
        self._set_progress_done(False)
        self.progress_bar.setFormat(f"已停止  {count:,} 条")
        self._update_export_buttons()
        self.status_changed.emit(f"已停止：共 {count:,} 条")

    def _on_clear(self):
        """清空结果"""
        self.all_passwords = []
        self.preview_text.clear()
        self._set_progress_done(False)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("待机")
        self._update_export_buttons()
        self.status_changed.emit("结果已清空")

    def _set_progress_done(self, done):
        """进度条颜色即状态：蓝色=进行中，绿色=完成"""
        self.progress_bar.setProperty("done", "true" if done else "false")
        style = self.progress_bar.style()
        style.unpolish(self.progress_bar)
        style.polish(self.progress_bar)

    def _on_batch_ready(self, batch):
        """批量结果就绪（忽略来自已废弃线程的迟到批次）"""
        if self.sender() is not self.generate_thread:
            return
        self.all_passwords.extend(batch)

        # 预览仅保留前 N 条；纯文本追加避免特殊字符被 HTML 解析
        remaining = PREVIEW_LINES - self.preview_text.blockCount()
        if remaining > 0:
            self.preview_text.appendPlainText('\n'.join(batch[:remaining]))

    def _on_progress(self, current, estimated):
        """更新进度"""
        if estimated > 0:
            pct = min(int(current / estimated * 100), 99)
            elapsed = time.monotonic() - getattr(self, '_started_at', time.monotonic())
            self.progress_bar.setValue(pct)
            self.progress_bar.setFormat(f"生成中 {pct}%  ·  {current:,}/{estimated:,}  ·  {elapsed:.0f}s")

    def _on_finished(self, count):
        """生成完成"""
        if self.sender() is not self.generate_thread:
            return
        elapsed = time.monotonic() - getattr(self, '_started_at', time.monotonic())
        self._set_progress_done(True)
        self.progress_bar.setValue(100)
        self.progress_bar.setFormat(f"完成  {count:,} 条  ·  用时 {elapsed:.1f}s")
        # 追加过程会自动滚到底部，完成后回到顶部方便从头查看
        self.preview_text.moveCursor(QTextCursor.Start)

        self.generate_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self._update_export_buttons()

        unique = len(set(self.all_passwords))
        message = (f"生成完成：共 {count:,} 条，去重后 {unique:,} 条"
                   + ("（已全部去重）" if unique == count else f"（重复 {count - unique:,} 条）"))
        # 自定义规则里引用了没填的字段时，整行会静默展开为空——这里点明是哪几个
        missing = getattr(self.generator, 'last_missing_placeholders', None)
        if missing:
            message += (f" · 自定义规则缺少「{'、'.join(sorted(missing))}」，"
                        "请补填对应信息后重新生成")
        self.status_changed.emit(message)

        self._record_history(count)

    def _record_history(self, count):
        """写入生成历史（失败静默，不影响主流程）"""
        try:
            from utils.history import save_history
            info = self._info_provider() if self._info_provider else {}
            rules = self._rules_provider() if self._rules_provider else {}
            parts = [info[k] for k in ('chinese_name', 'english_name', 'phone', 'birthday')
                     if info.get(k)]
            info_summary = ' / '.join(parts) or '（未填写）'

            rule_parts = [f"{rules.get('min_len', 5)}-{rules.get('max_len', 20)} 位",
                          f"{rules.get('max_depth', 3)} 级组合"]
            req = [label for key, label in (
                ('require_digit', '数字'), ('require_alpha', '字母'),
                ('require_special', '特殊字符'), ('require_mixed_case', '大小写混合'))
                if rules.get(key)]
            if req:
                rule_parts.append('+'.join(req))
            charset = rules.get('charset_mode', 'any')
            if charset == 'alnum':
                rule_parts.append('仅字母数字')
            elif charset == 'digit':
                rule_parts.append('仅数字')
            save_history(info_summary, ' / '.join(rule_parts), count)
        except Exception:
            pass

    def _on_error(self, msg):
        """生成出错"""
        QMessageBox.critical(self, "生成错误", f"生成过程中出错：{msg}")
        self.progress_bar.setFormat("出错")
        self.generate_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

    # ---------------------------------------------------------------- 状态

    def _update_export_buttons(self):
        has_result = len(self.all_passwords) > 0
        self.export_txt_btn.setEnabled(has_result)
        self.export_csv_btn.setEnabled(has_result)
        self.copy_btn.setEnabled(has_result)

    def _copy_all(self):
        """复制全部结果到剪贴板"""
        if not self.all_passwords:
            return
        QApplication.clipboard().setText('\n'.join(self.all_passwords))
        self.status_changed.emit(f"已复制 {len(self.all_passwords):,} 条到剪贴板")

    # ---------------------------------------------------------------- 导出

    def _save_path(self, title, default_name, filter_):
        last_dir = self._settings.value(LAST_DIR_KEY, "")
        filepath, _ = QFileDialog.getSaveFileName(
            self, title, os.path.join(last_dir, default_name) if last_dir else default_name,
            filter_
        )
        if filepath:
            self._settings.setValue(LAST_DIR_KEY, os.path.dirname(filepath))
        return filepath

    def _export_txt(self):
        """导出为TXT（含分片 / 可选分档 Top100、Top1000）"""
        if not self.all_passwords:
            return

        filepath = self._save_path("导出 TXT", "password_dict.txt", "文本文件 (*.txt)")
        if not filepath:
            return

        encoding = self.encoding_combo.currentText()
        split_size = self.split_spin.value() if self.split_check.isChecked() else None

        try:
            if self.tier_check.isChecked() and not split_size:
                from utils.exporter import export_tiers
                tiers = export_tiers(self.all_passwords, filepath, (100, 1000), encoding)
                lines = [f"{label}: {count:,} 条 → {os.path.basename(path)}"
                         for label, path, count in tiers]
                self.status_changed.emit(f"已分档导出 {len(tiers)} 个文件")
                QMessageBox.information(
                    self, "导出成功",
                    "已按优先级分档导出（命名后缀 _top100 / _top1000）：\n\n"
                    + "\n".join(lines)
                )
                return

            files = export_txt(self.all_passwords, filepath, encoding, split_size)
            self.status_changed.emit(f"已导出 {len(files)} 个TXT文件")
            QMessageBox.information(
                self, "导出成功",
                f"已导出到: {filepath}" + (f"\n共 {len(files)} 个分片文件" if len(files) > 1 else "")
            )
        except Exception as e:
            QMessageBox.critical(self, "导出失败", f"导出出错：{str(e)}")

    def _export_csv(self):
        """导出为CSV"""
        if not self.all_passwords:
            return

        filepath = self._save_path("导出 CSV", "password_dict.csv", "CSV文件 (*.csv)")
        if not filepath:
            return

        encoding = self.encoding_combo.currentText()
        try:
            export_csv(self.all_passwords, filepath, encoding)
            self.status_changed.emit("CSV导出完成")
            QMessageBox.information(
                self, "导出成功",
                f"已导出到: {filepath}\n\n"
                "Excel 兼容说明：\n"
                "• UTF-8 编码已带 BOM，中文表头不会乱码\n"
                "• 以 = + - @ 开头、前导零或超过 15 位的密码已加单引号前缀强制为文本，\n"
                "  Excel 中显示和复制都不含该引号\n\n"
                "给爆破工具用的字典请导出 TXT（TXT 不做任何转义）"
            )
        except Exception as e:
            QMessageBox.critical(self, "导出失败", f"导出出错：{str(e)}")
