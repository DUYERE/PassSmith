"""信息输入面板 - 采集目标个人信息"""

import re

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QGroupBox, QLabel, QLineEdit, QDateEdit, QCheckBox,
    QScrollArea, QPushButton
)
from PyQt5.QtCore import Qt, QDate, QTimer
from PyQt5.QtWidgets import QSizePolicy


def _validate_phone(text):
    """手机号：11 位数字（容忍 +86/86 前缀与分隔符）"""
    digits = re.sub(r'[\s\-]', '', text)
    digits = re.sub(r'^(\+?86)', '', digits)
    if not digits.isdigit() or len(digits) != 11:
        return False, '手机号应为 11 位数字'
    return True, ''


def _validate_idcard(text):
    """身份证：15 位数字，或 17 位数字 + 校验位 X/x"""
    s = text.strip().upper()
    if len(s) == 15 and s.isdigit():
        return True, ''
    if len(s) == 18 and s[:17].isdigit() and s[17] in '0123456789X':
        return True, ''
    return False, '身份证应为 15 位数字，或 17 位数字 + 校验位（X/x）'


def _validate_qq(text):
    """QQ：5-11 位纯数字"""
    if not text.strip().isdigit() or not 5 <= len(text.strip()) <= 11:
        return False, 'QQ 号应为 5-11 位纯数字'
    return True, ''


def _validate_email(text):
    """邮箱：包含 @，前后非空且不含空格"""
    if text.count('@') != 1 or not text.split('@')[0] or not text.split('@')[1]:
        return False, '邮箱格式应为「前缀@域名」'
    return True, ''


# 实时格式校验：错误输入会静默生成低质字典，必须当场标红提示
FIELD_VALIDATORS = {
    'phone': _validate_phone,
    'idcard': _validate_idcard,
    'qq': _validate_qq,
    'email': _validate_email,
}


class InfoInputPanel(QWidget):
    """信息输入面板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.fields = {}
        self.date_checks = {}  # 日期启用复选框
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

        # 面板说明 + 清空按钮
        head_layout = QHBoxLayout()
        head_label = QLabel("录入已知目标信息，信息越全，字典命中率越高")
        head_label.setProperty("role", "panelHint")
        head_layout.addWidget(head_label)
        head_layout.addStretch()

        clear_btn = QPushButton("清空输入")
        clear_btn.setProperty("variant", "ghost")
        clear_btn.setCursor(Qt.PointingHandCursor)
        clear_btn.setToolTip("清空所有已录入的信息")
        clear_btn.clicked.connect(self.clear_all)
        head_layout.addWidget(clear_btn)
        main_layout.addLayout(head_layout)

        # 基础身份 + 联系方式（并排）
        top_layout = QHBoxLayout()

        identity_group = QGroupBox("基础身份")
        # 核心分组：更亮的表面 + 左侧琥珀条，和其余四个分组拉开主次
        identity_group.setProperty("emphasis", "true")
        identity_layout = QGridLayout()
        identity_layout.setSpacing(8)

        self._add_field(identity_layout, 0, "中文姓名:", "chinese_name", "如 张三")
        self._add_field(identity_layout, 1, "英文姓名:", "english_name", "选填")
        self._add_field(identity_layout, 2, "昵称/别名:", "nickname", "选填")
        self._add_date_field(identity_layout, 3, "出生日期:", "birthday")

        identity_group.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        identity_group.setLayout(identity_layout)
        top_layout.addWidget(identity_group)

        contact_group = QGroupBox("联系方式")
        contact_layout = QGridLayout()
        contact_layout.setSpacing(8)

        self._add_field(contact_layout, 0, "手机号码:", "phone", "11位手机号")
        self._add_field(contact_layout, 1, "QQ号:", "qq", "选填")
        self._add_field(contact_layout, 2, "微信号:", "wechat", "选填")
        self._add_field(contact_layout, 3, "邮箱地址:", "email", "选填")

        contact_group.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        contact_group.setLayout(contact_layout)
        top_layout.addWidget(contact_group)

        main_layout.addLayout(top_layout)

        # 证件编号 + 工作/学校（并排）
        mid_layout = QHBoxLayout()

        id_group = QGroupBox("证件编号")
        id_layout = QGridLayout()
        id_layout.setSpacing(8)

        self._add_field(id_layout, 0, "身份证号:", "idcard", "15/18位")
        self._add_field(id_layout, 1, "工号:", "work_id", "选填")
        self._add_field(id_layout, 2, "学号:", "student_id", "选填")

        id_group.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        id_group.setLayout(id_layout)
        mid_layout.addWidget(id_group)

        work_group = QGroupBox("工作/学校")
        work_layout = QGridLayout()
        work_layout.setSpacing(8)

        self._add_field(work_layout, 0, "公司/学校:", "company", "选填")
        self._add_field(work_layout, 1, "缩写:", "company_abbr", "如 ZJU、HW")
        self._add_field(work_layout, 2, "所在城市:", "city", "选填")

        work_group.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        work_group.setLayout(work_layout)
        mid_layout.addWidget(work_group)

        main_layout.addLayout(mid_layout)

        # 社交关系（整行，3 列压缩到 2 行——原来 3 行会被滚动区裁掉一半）
        social_group = QGroupBox("社交关系（选填）")
        social_layout = QGridLayout()
        social_layout.setSpacing(8)

        self._add_field(social_layout, 0, "伴侣姓名:", "partner_name", "")
        self._add_date_field(social_layout, 0, "伴侣生日:", "partner_birthday", col=2)
        self._add_field(social_layout, 0, "父亲姓名:", "father_name", "", col=4)
        self._add_field(social_layout, 1, "母亲姓名:", "mother_name", "")
        self._add_field(social_layout, 1, "宠物名称:", "pet_name", "", col=2)
        self._add_field(social_layout, 1, "常用ID/用户名:", "username", "选填", col=4)

        social_group.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        social_group.setLayout(social_layout)
        self.social_group = social_group
        # 社会关系是选填项且整屏放不下：默认折叠，点标题展开。
        # 直接平铺会把整列撑到需要滚动，导出区被挤到视口外（按钮点不到）。
        social_group.setVisible(False)

        self.social_toggle = QPushButton("+   社交关系（选填）— 伴侣 / 父母 / 宠物 / 常用ID")
        self.social_toggle.setProperty("variant", "ghost")
        self.social_toggle.setProperty("role", "disclosure")
        self.social_toggle.setCheckable(True)
        self.social_toggle.setCursor(Qt.PointingHandCursor)
        # 宽度贴合文字：既实现左对齐，又不让按钮横贯整列
        self.social_toggle.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        self.social_toggle.toggled.connect(self._on_social_toggled)
        main_layout.addWidget(social_group)
        # 不加尾部 stretch：stretch 会把容器撑到视口高度，内容被压缩而不是滚动

        scroll.setWidget(container)

        self._scroll = scroll
        outer_layout = QVBoxLayout(self)
        # 底部留 4px：折叠标题紧贴下方分组边框会看起来像给按钮画了下划线
        outer_layout.setContentsMargins(0, 0, 0, 4)
        outer_layout.setSpacing(0)
        outer_layout.addWidget(scroll, 1)
        # 折叠标题固定在滚动区之外：无论内容是否滚动，用户总能看见并展开选填项
        outer_layout.addWidget(self.social_toggle)

    def _on_social_toggled(self, checked):
        """展开/收起社交关系分组"""
        self.social_group.setVisible(checked)
        self.social_toggle.setText(
            ("−   社交关系（选填）" if checked
             else "+   社交关系（选填）— 伴侣 / 父母 / 宠物 / 常用ID"))
        if checked:
            # 分组展开在滚动区底部，不主动滚动的话用户只能看到标题
            QTimer.singleShot(0, lambda: self._scroll.ensureWidgetVisible(self.social_group))

    def _add_field(self, layout, row, label_text, field_name, hint="", col=0):
        """添加一个输入字段"""
        label = QLabel(label_text)
        label.setProperty("role", "fieldLabel")
        layout.addWidget(label, row, col)

        field = QLineEdit()
        if hint:
            field.setPlaceholderText(hint)
        self.fields[field_name] = field
        layout.addWidget(field, row, col + 1)

        # 实时格式校验：错误输入静默产低质字典，必须当场标红提示
        if field_name in FIELD_VALIDATORS:
            field.textChanged.connect(lambda _=None, f=field, k=field_name: self._validate_field(f, k))

    @staticmethod
    def _validate_field(field, key):
        """单字段格式校验：不合法时标红并写 tooltip；空值视为合法（选填）"""
        ok, tip = FIELD_VALIDATORS[key](field.text())
        if field.text().strip():
            field.setProperty('invalid', 'false' if ok else 'true')
            field.setToolTip('' if ok else tip)
        else:
            field.setProperty('invalid', 'false')
            field.setToolTip('')
        style = field.style()
        style.unpolish(field)
        style.polish(field)

    def _add_date_field(self, layout, row, label_text, field_name, col=0):
        """添加一个日期选择字段（带启用复选框）"""
        label = QLabel(label_text)
        label.setProperty("role", "fieldLabel")
        layout.addWidget(label, row, col)

        date_widget = QDateEdit()
        date_widget.setCalendarPopup(True)
        date_widget.setDisplayFormat("yyyy-MM-dd")
        date_widget.setDate(QDate(1990, 1, 1))
        date_widget.setEnabled(False)

        check = QCheckBox("启用")
        check.toggled.connect(date_widget.setEnabled)

        h_layout = QHBoxLayout()
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(8)
        h_layout.addWidget(check)
        h_layout.addWidget(date_widget, 1)

        container = QWidget()
        container.setLayout(h_layout)

        self.fields[field_name] = date_widget
        self.date_checks[field_name] = check
        layout.addWidget(container, row, col + 1)

    def get_info_data(self):
        """获取所有输入信息"""
        data = {}
        for key, widget in self.fields.items():
            if isinstance(widget, QDateEdit):
                # 日期字段：只有在用户勾选启用时才返回
                if key in self.date_checks and self.date_checks[key].isChecked():
                    data[key] = widget.date().toString("yyyy-MM-dd")
            elif isinstance(widget, QLineEdit):
                text = widget.text().strip()
                if text:
                    data[key] = text
        return data

    def set_info_data(self, info_data):
        """按模板/批量数据回填输入框（缺失字段清空，日期字段按是否有值切换启用）"""
        info_data = info_data or {}
        for key, widget in self.fields.items():
            value = info_data.get(key, '')
            if isinstance(widget, QDateEdit):
                enabled = bool(value)
                if key in self.date_checks:
                    self.date_checks[key].setChecked(enabled)
                if enabled:
                    date = QDate.fromString(str(value), "yyyy-MM-dd")
                    if date.isValid():
                        widget.setDate(date)
            elif isinstance(widget, QLineEdit):
                widget.setText(str(value) if value else '')

    def clear_all(self):
        """清空所有输入"""
        for widget in self.fields.values():
            if isinstance(widget, QLineEdit):
                widget.clear()
            elif isinstance(widget, QDateEdit):
                widget.setDate(QDate(1990, 1, 1))
        for check in self.date_checks.values():
            check.setChecked(False)
