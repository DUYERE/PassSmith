"""工具对话框 - 批量生成 / 字典合并 / 模板管理 / 历史记录

四个功能共用一套「选文件 → 后台处理 → 进度反馈」的模式，
统一放在这里避免 ui 目录碎片化。
"""

import csv
import os
import time

from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QLineEdit, QListWidget, QListWidgetItem, QTableWidget, QTableWidgetItem,
    QFileDialog, QMessageBox, QProgressBar, QPlainTextEdit, QCheckBox,
    QAbstractItemView, QHeaderView, QGroupBox, QComboBox,
)

from core.combiner import PasswordGenerator
from utils.dict_ops import merge_passwords, diff_passwords
from utils.exporter import export_txt
from utils.history import load_history, clear_history
from utils.template_manager import (
    save_template, load_template, list_templates, delete_template, safe_template_name,
)

# 批量 CSV 支持的列：中文表头与内部字段名都认
BATCH_HEADERS = [
    ('姓名', 'chinese_name'), ('英文名', 'english_name'), ('昵称', 'nickname'),
    ('生日', 'birthday'), ('手机', 'phone'), ('身份证', 'idcard'),
    ('QQ', 'qq'), ('微信', 'wechat'), ('邮箱', 'email'),
    ('工号', 'work_id'), ('学号', 'student_id'),
    ('公司', 'company'), ('公司简称', 'company_abbr'), ('城市', 'city'),
    ('用户名', 'username'),
]
HEADER_MAP = {}
for _zh, _key in BATCH_HEADERS:
    HEADER_MAP[_zh] = _key
    HEADER_MAP[_key] = _key

SAMPLE_ROWS = [
    ['张三', '', '', '1990-01-15', '13812345678', '', '', '', '', '', '', '腾讯科技', 'TX', '深圳', 'zhangsan'],
    ['李雷', 'Leo Li', '雷子', '1988-07-02', '13900001111', '', '', '', '', '', '', '', '', '北京', ''],
]


def _normalize_date(text):
    """生日归一化为 yyyy-MM-dd

    直接复用 core 的解析器，保证批量 CSV 与单条输入的宽容度一致：
    `1990-01-15` / `1990/1/5` / `1990.1.5` / `1990年1月15日` / `19900115` / `90-01-15`
    全部归一为同一格式；非法日期（`1990-13-45`）与无法识别的写法返回空串。
    """
    from core.birthday_handler import _normalize_date_text, _valid_date

    normalized = _normalize_date_text((text or '').strip())
    if not normalized:
        return ''

    if '-' in normalized:
        parts = [p for p in normalized.split('-') if p]
        if len(parts) != 3:
            return ''
        year, month, day = parts
    else:
        digits = normalized
        if len(digits) == 8:
            year, month, day = digits[:4], digits[4:6], digits[6:8]
        elif len(digits) == 6:
            year, month, day = digits[:2], digits[2:4], digits[4:6]
        else:
            return ''

    # 两位年份补世纪（00-30 记作 20xx，其余 19xx），与单条输入的规则一致
    if len(year) == 2 and year.isdigit():
        yy = int(year)
        year = str(2000 + yy if yy <= 30 else 1900 + yy)

    if not _valid_date(year, month, day):
        return ''
    return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"


def _normalize_row(raw):
    """CSV 行 → info_data；未知列忽略，生日统一格式"""
    info = {}
    for header, value in raw.items():
        key = HEADER_MAP.get((header or '').strip())
        if not key:
            continue
        value = (value or '').strip()
        if not value:
            continue
        info[key] = _normalize_date(value) if key == 'birthday' else value
        if key == 'birthday' and not info[key]:
            info.pop(key, None)
    return info


def _safe_filename(text, fallback):
    """Windows 文件名安全化"""
    cleaned = ''.join(ch for ch in (text or '') if ch not in '\\/:*?"<>|').strip()
    return cleaned or fallback


class BatchWorker(QThread):
    """批量生成工作线程（逐目标生成并导出）"""

    progress = pyqtSignal(int, int, str)
    done = pyqtSignal(int, int, int)

    def __init__(self, rows, out_dir, rules_config, skip_existing=False, parent=None):
        super().__init__(parent)
        self.rows = rows
        self.out_dir = out_dir
        self.rules_config = rules_config
        self.skip_existing = skip_existing
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        generator = PasswordGenerator()
        ok = fail = skipped = 0
        total = len(self.rows)
        for i, info in enumerate(self.rows):
            if self._stop:
                break
            label = info.get('chinese_name') or info.get('phone') or f'row{i + 1}'
            try:
                name = _safe_filename(f"{i + 1:03d}_{label}", f"row{i + 1}")
                path = os.path.join(self.out_dir, f"{name}.txt")
                if self.skip_existing and os.path.exists(path):
                    skipped += 1
                    self.progress.emit(i + 1, total, f"{label}: 文件已存在，跳过")
                    continue
                passwords = list(generator.generate(info, self.rules_config))
                if not passwords:
                    fail += 1
                    self.progress.emit(i + 1, total, f"{label}: 无可用信息，跳过")
                    continue
                export_txt(passwords, path)
                ok += 1
                self.progress.emit(i + 1, total, f"{label}: {len(passwords):,} 条 → {os.path.basename(path)}")
            except Exception as exc:  # 单个目标失败不影响其余
                fail += 1
                self.progress.emit(i + 1, total, f"{label}: 失败（{exc}）")
        self.done.emit(ok, fail, skipped)


class BatchDialog(QDialog):
    """批量模式：CSV 多目标 → 每目标一个字典文件"""

    BASE_SIZE = (760, 560)

    def __init__(self, rules_provider, parent=None):
        super().__init__(parent)
        self._rules_provider = rules_provider
        self.rows = []
        self.worker = None
        self.setWindowTitle("批量生成")
        self.resize(*self.BASE_SIZE)
        self._init_ui()

    def apply_zoom(self, scale):
        """跟随主窗口缩放：窗口尺寸与固定像素高度控件等比调整（字号由全局 QSS 负责）"""
        self.resize(round(self.BASE_SIZE[0] * scale), round(self.BASE_SIZE[1] * scale))
        self.table.setMaximumHeight(round(180 * scale))
        self.log.setMinimumHeight(round(80 * scale))

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        file_group = QGroupBox("目标列表（CSV）")
        file_layout = QGridLayout()
        file_layout.setContentsMargins(0, 0, 0, 0)
        file_layout.setSpacing(6)

        self.csv_path_edit = QLineEdit()
        self.csv_path_edit.setReadOnly(True)
        self.csv_path_edit.setPlaceholderText("选择一个 CSV 文件，列名见下方说明")
        file_layout.addWidget(self.csv_path_edit, 0, 0, 1, 2)

        pick_btn = QPushButton("选择 CSV…")
        pick_btn.setProperty("variant", "ghost")
        pick_btn.clicked.connect(self._pick_csv)
        file_layout.addWidget(pick_btn, 0, 2)

        sample_btn = QPushButton("导出示例 CSV")
        sample_btn.setProperty("variant", "ghost")
        sample_btn.clicked.connect(self._save_sample)
        file_layout.addWidget(sample_btn, 0, 3)

        hint = QLabel("支持列：" + "、".join(zh for zh, _ in BATCH_HEADERS)
                      + "（留空列自动忽略；生日支持 1990-01-15 或 19900115）")
        hint.setProperty("role", "help")
        hint.setWordWrap(True)
        file_layout.addWidget(hint, 1, 0, 1, 4)

        self.out_dir_edit = QLineEdit()
        self.out_dir_edit.setReadOnly(True)
        self.out_dir_edit.setPlaceholderText("选择字典输出目录")
        file_layout.addWidget(self.out_dir_edit, 2, 0, 1, 2)
        dir_btn = QPushButton("输出目录…")
        dir_btn.setProperty("variant", "ghost")
        dir_btn.clicked.connect(self._pick_out_dir)
        file_layout.addWidget(dir_btn, 2, 2)
        file_group.setLayout(file_layout)
        layout.addWidget(file_group)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["#", "姓名", "手机", "生日"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setMaximumHeight(180)
        layout.addWidget(self.table)

        ctrl_row = QHBoxLayout()
        ctrl_row.setSpacing(6)
        self.start_btn = QPushButton("开始批量生成")
        self.start_btn.setProperty("variant", "primary")
        self.start_btn.setEnabled(False)
        self.start_btn.clicked.connect(self._start)
        self.stop_btn = QPushButton("停止")
        self.stop_btn.setProperty("variant", "danger")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._stop)
        close_btn = QPushButton("关闭")
        close_btn.setProperty("variant", "ghost")
        close_btn.clicked.connect(self.reject)
        ctrl_row.addWidget(self.start_btn)
        ctrl_row.addWidget(self.stop_btn)
        ctrl_row.addStretch()
        ctrl_row.addWidget(close_btn)
        layout.addLayout(ctrl_row)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setFormat("待机")
        layout.addWidget(self.progress)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setObjectName("Console")
        self.log.setPlaceholderText("生成日志将显示在这里…")
        layout.addWidget(self.log, 1)

    # ------------------------------------------------------------ 文件选择

    def _pick_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择目标列表", "", "CSV 文件 (*.csv);;所有文件 (*)")
        if not path:
            return
        try:
            self.rows = self._read_csv(path)
        except Exception as exc:
            QMessageBox.warning(self, "读取失败", f"无法读取 CSV：{exc}")
            return
        if not self.rows:
            QMessageBox.warning(self, "无有效数据", "CSV 中没有可识别的目标行。")
            return
        self.csv_path_edit.setText(path)
        self._fill_table()
        self._refresh_start_state()

    @staticmethod
    def _read_csv(path):
        """读取目标 CSV：自动尝试 UTF-8 / GBK / UTF-16

        Excel 中文环境「另存为 CSV」默认写 GBK，只按 UTF-8 解码会直接抛
        UnicodeDecodeError。反过来，用 GBK 去解 UTF-8 内容有时不报错却产出
        乱码，所以判据不能只看「有没有异常」——还要求表头能对上已知列名。
        """
        last_error = None
        decoded_ok = False
        for encoding in ('utf-8-sig', 'gbk', 'utf-16'):
            try:
                with open(path, 'r', encoding=encoding, newline='') as f:
                    reader = csv.DictReader(f)
                    headers = [(h or '').strip() for h in (reader.fieldnames or [])]
                    if not any(h in HEADER_MAP for h in headers):
                        # 解码没问题，只是列名对不上——不能算编码错误
                        decoded_ok = True
                        continue
                    rows = []
                    for raw in reader:
                        info = _normalize_row(raw)
                        if info:
                            rows.append(info)
                    return rows
            except UnicodeError as exc:  # UnicodeDecodeError 的基类
                last_error = exc
                continue

        if decoded_ok:
            raise ValueError(
                "CSV 表头不含任何已知列名。\n"
                "支持的中文表头：" + "、".join(zh for zh, _ in BATCH_HEADERS))
        raise ValueError(
            f"无法识别文件编码（已尝试 UTF-8 / GBK / UTF-16）：{last_error}")

    def _save_sample(self):
        path, _ = QFileDialog.getSaveFileName(self, "保存示例 CSV", "targets_sample.csv", "CSV 文件 (*.csv)")
        if not path:
            return
        with open(path, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([zh for zh, _ in BATCH_HEADERS])
            writer.writerows(SAMPLE_ROWS)
        QMessageBox.information(self, "已保存", f"示例文件：{path}")

    def _pick_out_dir(self):
        path = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if path:
            self.out_dir_edit.setText(path)
            self._refresh_start_state()

    def _fill_table(self):
        self.table.setRowCount(0)
        for i, info in enumerate(self.rows[:50]):
            self.table.insertRow(i)
            for col, value in enumerate([
                str(i + 1), info.get('chinese_name', ''), info.get('phone', ''), info.get('birthday', '')
            ]):
                self.table.setItem(i, col, QTableWidgetItem(value))
        if len(self.rows) > 50:
            self.log.appendPlainText(f"共 {len(self.rows)} 个目标（表格仅预览前 50 个）")

    def _refresh_start_state(self):
        self.start_btn.setEnabled(bool(self.rows) and bool(self.out_dir_edit.text()))

    # ---------------------------------------------------------------- 执行

    def _planned_paths(self):
        """批量生成将写入的文件路径（与 worker 的命名规则保持一致）"""
        out_dir = self.out_dir_edit.text()
        paths = []
        for i, info in enumerate(self.rows):
            label = info.get('chinese_name') or info.get('phone') or f'row{i + 1}'
            name = _safe_filename(f"{i + 1:03d}_{label}", f"row{i + 1}")
            paths.append(os.path.join(out_dir, f"{name}.txt"))
        return paths

    def _start(self):
        if not self.rows or not self.out_dir_edit.text():
            return

        # 覆盖保护：批量重跑会静默抹掉上次结果，必须先问
        existing = [p for p in self._planned_paths() if os.path.exists(p)]
        skip_existing = False
        if existing:
            ret = QMessageBox.question(
                self, "文件已存在",
                f"{len(existing)} 个目标的字典文件已存在于输出目录。\n\n"
                f"示例：{os.path.basename(existing[0])}\n\n"
                "「是」覆盖  「否」跳过已存在的  「取消」不执行",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
                QMessageBox.No,
            )
            if ret == QMessageBox.Cancel:
                return
            skip_existing = (ret == QMessageBox.No)

        rules = self._rules_provider()
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.progress.setRange(0, len(self.rows))
        self.progress.setValue(0)
        self.progress.setFormat("%v / %m")
        self.log.clear()

        self.worker = BatchWorker(self.rows, self.out_dir_edit.text(), rules,
                                  skip_existing=skip_existing, parent=self)
        self.worker.progress.connect(self._on_progress)
        self.worker.done.connect(self._on_done)
        self.worker.start()

    def _stop(self):
        if self.worker:
            self.worker.stop()
            self.log.appendPlainText("已请求停止，等待当前目标完成…")

    def _on_progress(self, current, total, message):
        self.progress.setValue(current)
        self.log.appendPlainText(f"[{current}/{total}] {message}")

    def _on_done(self, ok, fail, skipped=0):
        self.progress.setFormat("完成" if (fail == 0 and skipped == 0) else f"完成（{fail + skipped} 个未生成）")
        self.stop_btn.setEnabled(False)
        self._refresh_start_state()
        parts = [f"成功 {ok} 个"]
        if skipped:
            parts.append(f"跳过 {skipped} 个（已存在）")
        if fail:
            parts.append(f"失败/空 {fail} 个")
        self.log.appendPlainText("—— 完成：" + "，".join(parts) + " ——")

    def closeEvent(self, event):
        # 线程仍在运行时不能直接销毁对话框：QThread 随 parent 析构会 abort
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            if not self.worker.wait(5000):
                QMessageBox.information(
                    self, "正在收尾",
                    "当前目标尚在生成，请等这一条完成后再关闭窗口。")
                event.ignore()
                return
        super().closeEvent(event)


class MergeWorker(QThread):
    """字典合并/差集工作线程（逐行读入，避免一次性载入大文件）"""

    done = pyqtSignal(int, int, str)
    failed = pyqtSignal(str)

    def __init__(self, files, out_path, sort_by_len, mode='merge', parent=None):
        super().__init__(parent)
        self.files = files
        self.out_path = out_path
        self.sort_by_len = sort_by_len
        self.mode = mode  # 'merge' 并集去重 | 'diff' 差集（首个文件减去其余）
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        try:
            if self.mode == 'diff':
                result, base_count, exclude_count = diff_passwords(self.files[0], self.files[1:])
                header = (f"# 字典差集 - {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                          f"# 基准 {base_count:,} 条 - 排除 {exclude_count:,} 条 = {len(result):,} 条\n\n")
            else:
                result = merge_passwords(self.files)
                header = (f"# 合并字典 - {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                          f"# 总计: {len(result):,} 条（已去重）\n\n")

            # 读写阶段不可中断，但排序与落盘前可以放弃，避免关闭窗口后继续写
            if self._stop:
                self.failed.emit("已取消")
                return

            if self.sort_by_len:
                result.sort(key=lambda p: (len(p), p))

            with open(self.out_path, 'w', encoding='utf-8') as f:
                f.write(header)
                f.write('\n'.join(result) + ('\n' if result else ''))

            self.done.emit(len(self.files), len(result), self.out_path)
        except Exception as exc:
            self.failed.emit(str(exc))


class MergeDialog(QDialog):
    """字典合并/去重"""

    BASE_SIZE = (680, 480)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.files = []
        self.worker = None
        self.setWindowTitle("字典合并 / 去重")
        self.resize(*self.BASE_SIZE)
        self._init_ui()

    def apply_zoom(self, scale):
        self.resize(round(self.BASE_SIZE[0] * scale), round(self.BASE_SIZE[1] * scale))

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        mode_row = QHBoxLayout()
        mode_row.setSpacing(6)
        mode_label = QLabel("模式:")
        mode_label.setProperty("role", "fieldLabel")
        mode_row.addWidget(mode_label)
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("合并去重（所有文件求并集）", "merge")
        self.mode_combo.addItem("差集（第 1 个减去其余，用于排除已试密码）", "diff")
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        mode_row.addWidget(self.mode_combo, 1)
        layout.addLayout(mode_row)

        self.mode_hint = QLabel("合并模式：所有文件求并集后去重。")
        self.mode_hint.setProperty("role", "help")
        self.mode_hint.setWordWrap(True)
        layout.addWidget(self.mode_hint)

        top_row = QHBoxLayout()
        top_row.setSpacing(6)
        add_btn = QPushButton("添加字典文件…")
        add_btn.setProperty("variant", "ghost")
        add_btn.clicked.connect(self._add_files)
        clear_btn = QPushButton("清空列表")
        clear_btn.setProperty("variant", "ghost")
        clear_btn.clicked.connect(self._clear_files)
        top_row.addWidget(add_btn)
        top_row.addWidget(clear_btn)
        top_row.addStretch()
        self.sort_check = QCheckBox("按长度排序（短密码优先）")
        top_row.addWidget(self.sort_check)
        layout.addLayout(top_row)

        self.file_list = QListWidget()
        self.file_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        layout.addWidget(self.file_list, 1)

        out_row = QHBoxLayout()
        out_row.setSpacing(6)
        self.out_edit = QLineEdit()
        self.out_edit.setReadOnly(True)
        self.out_edit.setPlaceholderText("合并后的输出文件")
        out_row.addWidget(self.out_edit, 1)
        out_btn = QPushButton("输出到…")
        out_btn.setProperty("variant", "ghost")
        out_btn.clicked.connect(self._pick_out)
        out_row.addWidget(out_btn)
        layout.addLayout(out_row)

        ctrl_row = QHBoxLayout()
        ctrl_row.setSpacing(6)
        self.merge_btn = QPushButton("开始合并")
        self.merge_btn.setProperty("variant", "primary")
        self.merge_btn.setEnabled(False)
        self.merge_btn.clicked.connect(self._start)
        close_btn = QPushButton("关闭")
        close_btn.setProperty("variant", "ghost")
        close_btn.clicked.connect(self.reject)
        ctrl_row.addWidget(self.merge_btn)
        ctrl_row.addStretch()
        ctrl_row.addWidget(close_btn)
        layout.addLayout(ctrl_row)

        self.status = QLabel("尚未添加文件")
        self.status.setProperty("role", "help")
        layout.addWidget(self.status)

    def _add_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "选择字典文件", "", "字典文件 (*.txt *.csv *.lst);;所有文件 (*)")
        for path in paths:
            if path not in self.files:
                self.files.append(path)
        self._refresh()

    def _clear_files(self):
        self.files.clear()
        self._refresh()

    def _on_mode_changed(self):
        """切换模式：差集模式下首个文件是基准，其余是「已试过」的排除集"""
        if self.mode_combo.currentData() == 'diff':
            self.mode_hint.setText(
                "差集模式：第 1 个文件是主字典，其余文件视为「已试过」的密码并从主字典中剔除。"
                "用于二次爆破——已锁定的密码不再重复尝试，省账号锁定次数。"
            )
            self.merge_btn.setText("开始差集")
            self._pick_out_default = 'diff_dict.txt'
        else:
            self.mode_hint.setText("合并模式：所有文件求并集后去重。")
            self.merge_btn.setText("开始合并")
            self._pick_out_default = 'merged_dict.txt'
        self._refresh()

    def _refresh(self):
        self.file_list.clear()
        diff_mode = self.mode_combo.currentData() == 'diff'
        for i, path in enumerate(self.files):
            try:
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    count = sum(1 for _ in f)
            except OSError:
                count = -1
            prefix = ''
            if diff_mode:
                prefix = '【基准】' if i == 0 else '【排除】'
            item = QListWidgetItem(f"{prefix}{os.path.basename(path)}  ·  {count:,} 行" if count >= 0
                                   else f"{prefix}{os.path.basename(path)}  ·  无法读取")
            item.setToolTip(path)
            self.file_list.addItem(item)
        self.merge_btn.setEnabled(bool(self.files) and bool(self.out_edit.text()))
        if not self.files:
            self.status.setText("尚未添加文件")
        elif diff_mode:
            self.status.setText(f"基准 1 个 + 排除 {len(self.files) - 1} 个")
        else:
            self.status.setText(f"已添加 {len(self.files)} 个文件")

    def _pick_out(self):
        default = getattr(self, '_pick_out_default', 'merged_dict.txt')
        path, _ = QFileDialog.getSaveFileName(self, "合并输出", default, "文本文件 (*.txt)")
        if path:
            self.out_edit.setText(path)
            self._refresh()

    def _start(self):
        if not self.files or not self.out_edit.text():
            return
        if self.mode_combo.currentData() == 'diff' and len(self.files) < 2:
            QMessageBox.information(self, "需要至少两个文件",
                                    "差集模式需要：第 1 个是主字典，其余是「已试过」的排除字典。")
            return
        self.merge_btn.setEnabled(False)
        mode = self.mode_combo.currentData()
        self.status.setText("差集中…" if mode == 'diff' else "合并中…")
        self.worker = MergeWorker(self.files, self.out_edit.text(),
                                  self.sort_check.isChecked(), mode, self)
        self.worker.done.connect(self._on_done)
        self.worker.failed.connect(self._on_failed)
        self.worker.start()

    def _on_done(self, file_count, count, path):
        self.merge_btn.setEnabled(True)
        if self.mode_combo.currentData() == 'diff':
            self.status.setText(f"完成：差集后剩余 {count:,} 条 → {path}")
        else:
            self.status.setText(f"完成：{file_count} 个文件 → 去重后 {count:,} 条 → {path}")

    def _on_failed(self, message):
        self.merge_btn.setEnabled(True)
        if message == "已取消":
            self.status.setText("已取消")
            return
        self.status.setText("合并失败")
        QMessageBox.warning(self, "合并失败", message)

    def closeEvent(self, event):
        # 线程仍在运行时不能直接销毁对话框：QThread 随 parent 析构会 abort
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            if not self.worker.wait(5000):
                QMessageBox.information(
                    self, "正在收尾",
                    "字典仍在读写中，请稍候再关闭窗口。")
                event.ignore()
                return
        super().closeEvent(event)


class TemplateDialog(QDialog):
    """模板保存/加载/删除"""

    BASE_SIZE = (520, 400)

    def __init__(self, info_provider, rules_provider, info_applier, rules_applier, parent=None):
        super().__init__(parent)
        self._info_provider = info_provider
        self._rules_provider = rules_provider
        self._info_applier = info_applier
        self._rules_applier = rules_applier
        self.setWindowTitle("配置模板")
        self.resize(*self.BASE_SIZE)
        self._init_ui()
        self._refresh()

    def apply_zoom(self, scale):
        self.resize(round(self.BASE_SIZE[0] * scale), round(self.BASE_SIZE[1] * scale))

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QAbstractItemView.SingleSelection)
        layout.addWidget(self.list_widget, 1)

        save_row = QHBoxLayout()
        save_row.setSpacing(6)
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("模板名称，如：等保标准策略")
        save_row.addWidget(self.name_edit, 1)
        save_btn = QPushButton("保存当前配置")
        save_btn.setProperty("variant", "primary")
        save_btn.clicked.connect(self._save)
        save_row.addWidget(save_btn)
        layout.addLayout(save_row)

        ctrl_row = QHBoxLayout()
        ctrl_row.setSpacing(6)
        load_btn = QPushButton("加载选中模板")
        load_btn.clicked.connect(self._load)
        del_btn = QPushButton("删除选中")
        del_btn.setProperty("variant", "danger")
        del_btn.clicked.connect(self._delete)
        close_btn = QPushButton("关闭")
        close_btn.setProperty("variant", "ghost")
        close_btn.clicked.connect(self.reject)
        ctrl_row.addWidget(load_btn)
        ctrl_row.addWidget(del_btn)
        ctrl_row.addStretch()
        ctrl_row.addWidget(close_btn)
        layout.addLayout(ctrl_row)

        self.status = QLabel("模板保存在 output/templates/")
        self.status.setProperty("role", "help")
        layout.addWidget(self.status)

    def _refresh(self):
        self.list_widget.clear()
        for item in list_templates():
            name = item['name']
            row = QListWidgetItem(f"{name}（{len(item.get('info_keys', []))} 个字段）")
            # 真实名称存 UserRole：显示文本里带全角括号，从文本反解会把
            # 「等保（三级）」截成「等保」，导致加载/删除命中错误模板
            row.setData(Qt.UserRole, name)
            self.list_widget.addItem(row)
        if not self.list_widget.count():
            self.status.setText("暂无模板，先配置好信息和规则再保存")

    def _save(self):
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.information(self, "需要名称", "请输入模板名称。")
            return
        # 同名模板会直接覆盖 JSON，先确认一次
        cleaned = safe_template_name(name)
        if cleaned in {t['name'] for t in list_templates()}:
            if QMessageBox.question(
                    self, "模板已存在",
                    f"模板「{cleaned}」已存在，覆盖原内容？") != QMessageBox.Yes:
                return
        try:
            path = save_template(name, self._info_provider(), self._rules_provider())
        except Exception as exc:
            QMessageBox.warning(self, "保存失败", str(exc))
            return
        self.name_edit.clear()
        self._refresh()
        self.status.setText(f"已保存：{path}")

    def _selected_name(self):
        item = self.list_widget.currentItem()
        return item.data(Qt.UserRole) if item else None

    def _load(self):
        item = self.list_widget.currentItem()
        if not item:
            QMessageBox.information(self, "未选择", "请先选中一个模板。")
            return
        name = self._selected_name()
        data = load_template(name)
        if not data:
            QMessageBox.warning(self, "加载失败", "模板文件不存在或已损坏。")
            return
        self._info_applier(data.get('info_data') or {})
        self._rules_applier(data.get('rules_config') or {})
        self.status.setText(f"已加载模板：{name}")

    def _delete(self):
        item = self.list_widget.currentItem()
        if not item:
            return
        name = self._selected_name()
        if QMessageBox.question(self, "确认删除", f"删除模板「{name}」？") != QMessageBox.Yes:
            return
        delete_template(name)
        self._refresh()
        self.status.setText(f"已删除：{name}")


class HistoryDialog(QDialog):
    """生成历史记录"""

    BASE_SIZE = (760, 400)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("生成历史")
        self.resize(*self.BASE_SIZE)
        self._init_ui()
        self._refresh()

    def apply_zoom(self, scale):
        self.resize(round(self.BASE_SIZE[0] * scale), round(self.BASE_SIZE[1] * scale))

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["时间", "条数", "目标信息", "规则摘要"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        layout.addWidget(self.table, 1)

        ctrl_row = QHBoxLayout()
        ctrl_row.setSpacing(6)
        clear_btn = QPushButton("清空历史")
        clear_btn.setProperty("variant", "danger")
        clear_btn.clicked.connect(self._clear)
        close_btn = QPushButton("关闭")
        close_btn.setProperty("variant", "ghost")
        close_btn.clicked.connect(self.reject)
        ctrl_row.addWidget(clear_btn)
        ctrl_row.addStretch()
        ctrl_row.addWidget(close_btn)
        layout.addLayout(ctrl_row)

    def _refresh(self):
        records = load_history()
        self.table.setRowCount(0)
        for row, rec in enumerate(records):
            self.table.insertRow(row)
            values = [rec.get('timestamp', ''), f"{rec.get('count', 0):,}",
                      rec.get('info_summary', ''), rec.get('rules_summary', '')]
            for col, value in enumerate(values):
                self.table.setItem(row, col, QTableWidgetItem(str(value)))

    def _clear(self):
        if QMessageBox.question(self, "确认清空", "清空全部历史记录？") != QMessageBox.Yes:
            return
        clear_history()
        self._refresh()
