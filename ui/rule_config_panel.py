"""规则配置面板 - 快捷模式和高级模式"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QGroupBox, QLabel, QCheckBox, QSpinBox, QPushButton,
    QTextEdit, QRadioButton, QButtonGroup, QScrollArea, QComboBox
)
from PyQt5.QtCore import Qt, pyqtSignal

from core.util import load_config_file, split_list_text

# 站点密码策略预设：(key, 按钮文案, tooltip)
# 不同目标系统的策略差异极大，手动调 5 个控件太慢，点一下就套用
POLICY_PRESETS = [
    ("loose", "宽松", "任意策略：≥5 位，不做复杂度限制"),
    ("standard", "标准", "等保/AD 常见策略：≥8 位，大小写+数字+特殊字符"),
    ("alnum", "字母数字", "内网/老系统：≤16 位，仅字母数字，禁特殊字符"),
    ("pin", "数字 PIN", "锁屏/支付：4-8 位纯数字"),
]

# config 缺失时的兜底默认值（正常情况下列表从 config/*.txt 读取，避免双写不一致）
_FALLBACK_WEAK = ("123456, 12345678, 123456789, 520, 1314, 111111, 000000, "
                  "1234567, 12345, 1234, 123, 666, 888, 999, 000, "
                  "password, qwerty, abc123, admin, root, test, iloveyou, "
                  "welcome, master, a123456, qq123456, woaini1314, 147258, 1qaz2wsx")
_FALLBACK_SEPARATORS = "., _, -, @, #"


def _config_default(filename, fallback):
    """从 config 目录读取默认值（行式 → 逗号连接），缺失时用兜底串"""
    items = load_config_file(filename)
    return ', '.join(items) if items else fallback


class RuleConfigPanel(QWidget):
    """规则配置面板"""

    config_changed = pyqtSignal()

    QUICK_RULES = [
        ("name_weak", "姓名+弱口令组合", True),
        ("name_birthday", "姓名+生日组合", True),
        ("phone_variants", "手机号衍生组合", True),
        ("idcard_variants", "身份证后4/6/8位", True),
        ("name_special", "姓名拼音+特殊字符", True),
        ("case_variants", "大小写组合 (zs/Zs/ZS)", True),
        ("name_initial_num", "姓名首字母+数字组合", False),
        ("email_prefix", "邮箱前缀衍生", False),
        ("work_student_id", "工号/学号衍生", False),
        ("leet_speak", "Leet Speak 替换", False),
        ("keyboard_pattern", "常见键盘模式", False),
    ]

    # 高级模式文本框的基准高度（跟随缩放）
    TEXT_BASE_HEIGHTS = {'weak_pwd_edit': 72, 'sep_edit': 40, 'custom_rule_edit': 84}

    # 自定义规则编辑器的默认规则（首字母 + 弱口令 + 结尾特殊字符，如 zs123@）
    DEFAULT_CUSTOM_RULES = "{姓名首字母}{弱口令}{分隔符}"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        container = QWidget()
        main_layout = QVBoxLayout(container)
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(0, 2, 2, 2)

        # 模式选择
        mode_layout = QHBoxLayout()
        mode_label = QLabel("规则配置:")
        mode_label.setProperty("role", "fieldLabel")
        mode_layout.addWidget(mode_label)

        self.quick_mode_radio = QRadioButton("快捷模式")
        self.advanced_mode_radio = QRadioButton("高级模式")
        self.quick_mode_radio.setChecked(True)

        mode_group = QButtonGroup(self)
        mode_group.addButton(self.quick_mode_radio)
        mode_group.addButton(self.advanced_mode_radio)

        self.quick_mode_radio.toggled.connect(self._on_mode_changed)

        mode_layout.addWidget(self.quick_mode_radio)
        mode_layout.addWidget(self.advanced_mode_radio)
        mode_layout.addStretch()
        main_layout.addLayout(mode_layout)

        # 快捷模式勾选区
        self.quick_group = QGroupBox("快捷勾选")
        quick_layout = QGridLayout()
        quick_layout.setSpacing(6)

        self.quick_checks = {}
        for i, (key, text, default) in enumerate(self.QUICK_RULES):
            cb = QCheckBox(text)
            cb.setChecked(default)
            cb.stateChanged.connect(self.config_changed.emit)
            self.quick_checks[key] = cb
            quick_layout.addWidget(cb, i // 2, i % 2)

        # 长标签的示例说明放 tooltip，避免撑宽两列网格
        self.quick_checks['leet_speak'].setToolTip("如 a→@, e→3, i→1, o→0, s→$, t→7")
        self.quick_checks['keyboard_pattern'].setToolTip("qwerty、1234qwer、1qaz2wsx 等")

        # 说明卡放进勾选组内部末尾（跨两列）：视觉上归属勾选区，不留游离卡片
        self.quick_tip = QLabel(
            "当前为快捷模式：勾选常用规则即可生成。"
            "切换「高级模式」可精细控制长度、深度、弱口令、分隔符与自定义规则。"
        )
        self.quick_tip.setObjectName("QuickTip")
        self.quick_tip.setWordWrap(True)
        tip_row = len(self.QUICK_RULES) // 2 + len(self.QUICK_RULES) % 2
        quick_layout.addWidget(self.quick_tip, tip_row, 0, 1, 2)

        self.quick_group.setLayout(quick_layout)
        main_layout.addWidget(self.quick_group)

        # ===== 高级配置区（高级模式可见）=====
        self.advanced_widget = QWidget()
        adv_layout = QVBoxLayout(self.advanced_widget)
        adv_layout.setSpacing(8)
        adv_layout.setContentsMargins(0, 0, 0, 0)

        # 长度限制 + 组合深度（两行网格，避免最小宽度过大把面板撑出横向裁切）
        len_group = QGroupBox("长度与深度")
        len_layout = QGridLayout()
        len_layout.setSpacing(6)

        len_layout.addWidget(QLabel("最小长度:"), 0, 0)
        self.min_len_spin = QSpinBox()
        self.min_len_spin.setRange(1, 50)
        self.min_len_spin.setValue(5)
        len_layout.addWidget(self.min_len_spin, 0, 1)

        len_layout.addWidget(QLabel("最大长度:"), 0, 2)
        self.max_len_spin = QSpinBox()
        self.max_len_spin.setRange(1, 100)
        self.max_len_spin.setValue(20)
        len_layout.addWidget(self.max_len_spin, 0, 3)

        len_layout.addWidget(QLabel("组合深度:"), 1, 0)
        self.depth_spin = QSpinBox()
        self.depth_spin.setRange(1, 4)
        self.depth_spin.setValue(3)
        len_layout.addWidget(self.depth_spin, 1, 1)

        depth_hint = QLabel("(≤4，否则字典膨胀过快)")
        depth_hint.setProperty("role", "hint2")
        len_layout.addWidget(depth_hint, 1, 2, 1, 2)
        len_layout.setColumnStretch(1, 1)
        len_layout.setColumnStretch(3, 1)

        len_group.setLayout(len_layout)
        adv_layout.addWidget(len_group)

        # 弱口令编辑
        weak_group = QGroupBox("自定义弱口令（逗号或换行分隔）")
        weak_layout = QVBoxLayout()
        self.weak_pwd_edit = QTextEdit()
        self.weak_pwd_edit.setMaximumHeight(self.TEXT_BASE_HEIGHTS['weak_pwd_edit'])
        self.weak_pwd_edit.setPlainText(_config_default('weak_passwords.txt', _FALLBACK_WEAK))
        weak_layout.addWidget(self.weak_pwd_edit)
        weak_group.setLayout(weak_layout)
        adv_layout.addWidget(weak_group)

        # 分隔符
        sep_group = QGroupBox("自定义分隔符（逗号分隔）")
        sep_layout = QVBoxLayout()
        self.sep_edit = QTextEdit()
        self.sep_edit.setMaximumHeight(self.TEXT_BASE_HEIGHTS['sep_edit'])
        self.sep_edit.setPlainText(_config_default('separators.txt', _FALLBACK_SEPARATORS))
        sep_layout.addWidget(self.sep_edit)
        sep_group.setLayout(sep_layout)
        adv_layout.addWidget(sep_group)

        # 自定义规则编辑器
        rule_group = QGroupBox("自定义规则编辑器")
        rule_layout = QVBoxLayout()

        rule_help = QLabel(
            "占位符: {姓名} {姓} {名} {姓名首字母} {姓名变体} {生日全} {生日年} {生日月日} "
            "{生日短} {手机号} {手机后4} {手机后6} {身份证后4} {身份证后6} "
            "{工号} {学号} {邮箱前缀} {弱口令} {前缀} {后缀} {分隔符}\n"
            "注意: 单个占位符最多展开 32 个变体，超出部分忽略"
        )
        rule_help.setProperty("role", "help")
        rule_help.setWordWrap(True)
        rule_layout.addWidget(rule_help)

        self.custom_rule_edit = QTextEdit()
        self.custom_rule_edit.setMaximumHeight(self.TEXT_BASE_HEIGHTS['custom_rule_edit'])
        self.custom_rule_edit.setPlaceholderText(
            "每行一条规则，# 开头为注释，示例:\n{姓名}{生日年}\n{姓名首字母}{生日月日}\n{邮箱前缀}{弱口令}"
        )
        self.custom_rule_edit.setPlainText(self.DEFAULT_CUSTOM_RULES)
        rule_layout.addWidget(self.custom_rule_edit)
        rule_group.setLayout(rule_layout)
        adv_layout.addWidget(rule_group)

        # 站点策略预设：不同目标的密码策略差异很大，手动调 5 个控件太慢
        policy_group = QGroupBox("站点密码策略")
        policy_layout = QVBoxLayout()
        policy_layout.setContentsMargins(0, 0, 0, 0)
        policy_layout.setSpacing(6)

        preset_row = QHBoxLayout()
        preset_row.setContentsMargins(0, 0, 0, 0)
        preset_row.setSpacing(6)
        preset_hint = QLabel("预设:")
        preset_hint.setProperty("role", "fieldLabel")
        preset_row.addWidget(preset_hint)

        self.policy_buttons = {}
        for key, label, tip in POLICY_PRESETS:
            btn = QPushButton(label)
            btn.setProperty("variant", "ghost")
            btn.setCursor(Qt.PointingHandCursor)
            btn.setToolTip(tip)
            btn.clicked.connect(lambda _=None, k=key: self._apply_preset(k))
            self.policy_buttons[key] = btn
            preset_row.addWidget(btn)
        preset_row.addStretch()
        policy_layout.addLayout(preset_row)

        charset_row = QHBoxLayout()
        charset_row.setContentsMargins(0, 0, 0, 0)
        charset_row.setSpacing(6)
        charset_label = QLabel("字符集:")
        charset_label.setProperty("role", "fieldLabel")
        charset_row.addWidget(charset_label)
        self.charset_combo = QComboBox()
        self.charset_combo.addItem("任意字符（默认）", "any")
        self.charset_combo.addItem("仅字母数字（禁特殊字符）", "alnum")
        self.charset_combo.addItem("仅数字（PIN 码）", "digit")
        charset_row.addWidget(self.charset_combo, 1)
        policy_layout.addLayout(charset_row)

        policy_group.setLayout(policy_layout)
        adv_layout.addWidget(policy_group)

        # 筛选选项（去重为固定行为，见组标题说明；两列网格防撑宽）
        filter_group = QGroupBox("复杂度筛选（结果自动去重）")
        filter_layout = QGridLayout()
        filter_layout.setSpacing(6)

        self.require_digit_check = QCheckBox("必须包含数字")
        filter_layout.addWidget(self.require_digit_check, 0, 0)

        self.require_alpha_check = QCheckBox("必须包含字母")
        filter_layout.addWidget(self.require_alpha_check, 0, 1)

        self.require_special_check = QCheckBox("必须包含特殊字符")
        filter_layout.addWidget(self.require_special_check, 1, 0)

        self.require_mixed_check = QCheckBox("必须大小写混合")
        filter_layout.addWidget(self.require_mixed_check, 1, 1)

        filter_layout.setColumnStretch(0, 1)
        filter_layout.setColumnStretch(1, 1)
        filter_group.setLayout(filter_layout)
        adv_layout.addWidget(filter_group)

        self.advanced_widget.setVisible(False)
        main_layout.addWidget(self.advanced_widget)

        # 策略速览贴在面板底部：填充空白，并让用户在改完参数后一眼确认当前生效配置
        main_layout.addStretch()
        main_layout.addWidget(self._build_summary_group())
        self.config_changed.connect(self._refresh_summary)
        self._refresh_summary()

        scroll.setWidget(container)

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(scroll)

        self._connect_all_signals()

    def _connect_all_signals(self):
        """所有会影响生成结果的控件都发出 config_changed"""
        self.min_len_spin.valueChanged.connect(self._on_min_len_changed)
        self.max_len_spin.valueChanged.connect(self._on_max_len_changed)
        self.depth_spin.valueChanged.connect(self.config_changed.emit)
        self.weak_pwd_edit.textChanged.connect(self.config_changed.emit)
        self.sep_edit.textChanged.connect(self.config_changed.emit)
        self.custom_rule_edit.textChanged.connect(self.config_changed.emit)

        for check in (self.require_digit_check, self.require_alpha_check,
                      self.require_special_check, self.require_mixed_check):
            check.stateChanged.connect(self.config_changed.emit)

        self.charset_combo.currentIndexChanged.connect(self.config_changed.emit)

        # 防呆联动：要求大小写混合却没开大小写变体，输出会为 0 条
        self.require_mixed_check.toggled.connect(self._on_mixed_toggled)
        self.quick_checks['case_variants'].toggled.connect(self._on_case_variants_toggled)

    def _on_mode_changed(self, checked):
        """快捷模式仅显示勾选区；高级模式额外展开全部精细配置"""
        advanced = self.advanced_mode_radio.isChecked()
        self.advanced_widget.setVisible(advanced)
        self.quick_tip.setVisible(not advanced)

    def _build_summary_group(self):
        """底部的策略速览：四行读数，随配置实时刷新"""
        group = QGroupBox("当前策略")
        layout = QGridLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(14)
        layout.setVerticalSpacing(5)

        self.summary_labels = {}
        for row, (key, caption) in enumerate((
            ('len', '长度'), ('depth', '组合深度'),
            ('charset', '字符集'), ('rules', '生效规则'),
        )):
            cap = QLabel(caption)
            cap.setProperty("role", "panelHint")
            val = QLabel("—")
            val.setProperty("role", "metric")
            layout.addWidget(cap, row, 0)
            layout.addWidget(val, row, 1)
            self.summary_labels[key] = val

        layout.setColumnStretch(1, 1)
        group.setLayout(layout)
        return group

    def _refresh_summary(self):
        """刷新策略速览读数（不触发 config_changed，避免循环）"""
        if not getattr(self, 'summary_labels', None):
            return
        custom_lines = [ln.strip() for ln in self.custom_rule_edit.toPlainText().splitlines()]
        custom_count = sum(1 for ln in custom_lines if ln and not ln.startswith('#'))
        quick_count = sum(1 for cb in self.quick_checks.values() if cb.isChecked())

        self.summary_labels['len'].setText(
            f"{self.min_len_spin.value()} – {self.max_len_spin.value()} 位")
        self.summary_labels['depth'].setText(f"{self.depth_spin.value()} 级")
        self.summary_labels['charset'].setText(self.charset_combo.currentText())
        rules_text = f"{quick_count} 项快捷"
        if custom_count:
            rules_text += f" + {custom_count} 条自定义"
        self.summary_labels['rules'].setText(rules_text)

    def _on_min_len_changed(self, value):
        """下限超过上限时自动抬升上限——否则生成结果恒为 0 条，用户只会以为工具坏了"""
        if value > self.max_len_spin.value():
            self.max_len_spin.setValue(value)
        self.config_changed.emit()

    def _on_max_len_changed(self, value):
        """上限低于下限时自动下调下限"""
        if value < self.min_len_spin.value():
            self.min_len_spin.setValue(value)
        self.config_changed.emit()

    def _on_mixed_toggled(self, checked):
        """要求大小写混合 → 必须开启大小写变体，否则生成端没有大写形态可用"""
        if checked:
            self.quick_checks['case_variants'].setChecked(True)

    def _on_case_variants_toggled(self, checked):
        """关闭大小写变体 → 大小写混合要求失去意义，自动取消"""
        if not checked and self.require_mixed_check.isChecked():
            self.require_mixed_check.setChecked(False)

    # ---------------------------------------------------------------- 策略预设

    def _apply_preset(self, key):
        """套用站点密码策略预设：长度区间 + 复杂度要求 + 字符集 + 大小写组合联动"""
        presets = {
            'loose':    dict(min_len=5, max_len=20, digit=False, alpha=False,
                             special=False, mixed=False, charset=0, case=True),
            'standard': dict(min_len=8, max_len=20, digit=True, alpha=True,
                             special=True, mixed=True, charset=0, case=True),
            'alnum':    dict(min_len=6, max_len=16, digit=True, alpha=True,
                             special=False, mixed=False, charset=1, case=True),
            'pin':      dict(min_len=4, max_len=8, digit=True, alpha=False,
                             special=False, mixed=False, charset=2, case=False),
        }
        p = presets.get(key)
        if not p:
            return
        self.min_len_spin.setValue(p['min_len'])
        self.max_len_spin.setValue(p['max_len'])
        self.require_digit_check.setChecked(p['digit'])
        self.require_alpha_check.setChecked(p['alpha'])
        self.require_special_check.setChecked(p['special'])
        self.require_mixed_check.setChecked(p['mixed'])
        self.charset_combo.setCurrentIndex(p['charset'])
        # 要求大小写混合时，必须开启大小写变体生成，否则没有大写形态可用
        self.quick_checks['case_variants'].setChecked(p['case'])
        self.config_changed.emit()

    def apply_zoom(self, scale):
        """缩放支持：高级模式文本框高度按基准值等比缩放"""
        for name, base in self.TEXT_BASE_HEIGHTS.items():
            getattr(self, name).setMaximumHeight(round(base * scale))

    def set_rules_config(self, rules_config):
        """按模板回填规则配置（缺失项保持当前值）"""
        if not rules_config:
            return
        self.min_len_spin.setValue(int(rules_config.get('min_len', 5)))
        self.max_len_spin.setValue(int(rules_config.get('max_len', 20)))
        self.depth_spin.setValue(int(rules_config.get('max_depth', 3)))

        for key, cb in self.quick_checks.items():
            cb.setChecked(bool(rules_config.get('quick_rules', {}).get(key, cb.isChecked())))

        self.custom_rule_edit.setPlainText(rules_config.get('custom_rules') or '')

        self.require_digit_check.setChecked(bool(rules_config.get('require_digit')))
        self.require_alpha_check.setChecked(bool(rules_config.get('require_alpha')))
        self.require_special_check.setChecked(bool(rules_config.get('require_special')))
        self.require_mixed_check.setChecked(bool(rules_config.get('require_mixed_case')))

        charset = rules_config.get('charset_mode', 'any')
        idx = self.charset_combo.findData(charset)
        if idx >= 0:
            self.charset_combo.setCurrentIndex(idx)

        weak = rules_config.get('weak_passwords')
        if weak:
            self.weak_pwd_edit.setPlainText(', '.join(weak))
        seps = rules_config.get('separators')
        if seps:
            self.sep_edit.setPlainText(', '.join(seps))

        # 模板 JSON 被手工改过时可能出现矛盾组合：要求大小写混合、却关闭了
        # 大小写变体。此时生成端只有小写形态，出口过滤会把全部条目挡掉，
        # 表现为「加载模板后一条都生成不出来」。加载后强制校正回一致状态。
        if (self.require_mixed_check.isChecked()
                and not self.quick_checks['case_variants'].isChecked()):
            self.quick_checks['case_variants'].setChecked(True)

        self.config_changed.emit()

    def get_rules_config(self):
        """获取规则配置"""
        quick_rules = {key: cb.isChecked() for key, cb in self.quick_checks.items()}

        # 解析弱口令（兼容中英文逗号/顿号/分号/换行；空格不算——密码可能含空格）
        weak_passwords = split_list_text(self.weak_pwd_edit.toPlainText())

        # 解析分隔符（同上，且允许空格分隔——分隔符都是单字符符号，不含空格）
        separators = split_list_text(self.sep_edit.toPlainText(), allow_space=True)

        return {
            'max_depth': self.depth_spin.value(),
            'min_len': self.min_len_spin.value(),
            'max_len': self.max_len_spin.value(),
            'quick_rules': quick_rules,
            'custom_rules': self.custom_rule_edit.toPlainText(),
            'require_digit': self.require_digit_check.isChecked(),
            'require_alpha': self.require_alpha_check.isChecked(),
            'require_special': self.require_special_check.isChecked(),
            'require_mixed_case': self.require_mixed_check.isChecked(),
            'charset_mode': self.charset_combo.currentData(),
            'weak_passwords': weak_passwords,
            'separators': separators,
        }
