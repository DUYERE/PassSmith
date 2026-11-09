"""导出与模板工具测试：分档导出、覆盖行为、模板名安全化"""

import csv
import os

import pytest

from utils.exporter import export_txt, export_csv, export_tiers, format_size
from utils.template_manager import (
    save_template, load_template, list_templates, delete_template,
    safe_template_name, TEMPLATE_DIR,
)


# ------------------------------------------------------------------ 导出

def test_export_txt_content(tmp_path):
    path = str(tmp_path / 'dict.txt')
    export_txt(['abc123', 'zs520!'], path)
    lines = open(path, encoding='utf-8').read().splitlines()
    body = [l for l in lines if l and not l.startswith('#')]
    assert body == ['abc123', 'zs520!']


def test_export_txt_header(tmp_path):
    """导出文件必须带授权声明头，避免字典被当作攻击工具外传时无免责说明"""
    path = str(tmp_path / 'dict.txt')
    export_txt(['abc123'], path)
    text = open(path, encoding='utf-8').read()
    assert '仅供授权安全测试' in text
    assert '总计: 1 条' in text


def test_export_txt_split(tmp_path):
    path = str(tmp_path / 'dict.txt')
    files = export_txt([f'pw{i}' for i in range(25)], path, split_size=10)
    assert len(files) == 3
    assert all(os.path.exists(f) for f in files)


def test_export_txt_empty(tmp_path):
    assert export_txt([], str(tmp_path / 'x.txt')) == []


def test_export_tiers(tmp_path):
    """分档导出：Top100 / Top1000 / 全量，顺序与条数必须严格对应"""
    path = str(tmp_path / 'd.txt')
    passwords = [f'pw{i:04d}' for i in range(1500)]
    tiers = export_tiers(passwords, path)
    labels = [t[0] for t in tiers]
    assert labels == ['Top 100', 'Top 1000', '全量']

    top100_path = tiers[0][1]
    assert top100_path.endswith('_top100.txt')
    body = [l for l in open(top100_path, encoding='utf-8').read().splitlines()
            if l and not l.startswith('#')]
    assert len(body) == 100
    assert body[0] == 'pw0000'

    full = [l for l in open(path, encoding='utf-8').read().splitlines()
            if l and not l.startswith('#')]
    assert len(full) == 1500


def test_export_tiers_small_dict(tmp_path):
    """少于 100 条时只产出全量，不生成无意义的空档文件"""
    path = str(tmp_path / 'd.txt')
    tiers = export_tiers(['a', 'b'], path)
    assert [t[0] for t in tiers] == ['全量']


def test_export_csv_single_column(tmp_path):
    path = str(tmp_path / 'd.csv')
    export_csv(['abc123', 'zs520!'], path)
    lines = open(path, encoding='utf-8-sig').read().splitlines()
    assert lines[0] == '密码'
    assert lines[1:] == ['abc123', 'zs520!']


def test_export_csv_has_utf8_bom(tmp_path):
    """CSV 必须带 UTF-8 BOM：否则 Excel 按 GBK 解析，中文表头乱码"""
    path = str(tmp_path / 'd.csv')
    export_csv(['abc123'], path)
    raw = open(path, 'rb').read()
    assert raw.startswith(b'\xef\xbb\xbf')


def test_export_csv_gbk_no_bom(tmp_path):
    """选 GBK 编码时不能加 UTF-8 BOM（否则文件同时含两种编码，全废）"""
    path = str(tmp_path / 'd.csv')
    export_csv(['abc123'], path, encoding='GBK')
    raw = open(path, 'rb').read()
    assert not raw.startswith(b'\xef\xbb\xbf')
    assert '密码' in raw.decode('gbk')


def test_export_txt_never_has_bom(tmp_path):
    """TXT 绝不能带 BOM——BOM 会被爆破工具当成第一条密码的一部分"""
    path = str(tmp_path / 'd.txt')
    export_txt(['abc123'], path)
    raw = open(path, 'rb').read()
    assert not raw.startswith(b'\xef\xbb\xbf')


def test_export_csv_guards_formula_prefix(tmp_path):
    """Excel 会把 = + - @ 开头当公式，必须加单引号强制文本（CSV 注入防护）"""
    path = str(tmp_path / 'd.csv')
    export_csv(['=zhangsan', '-zhangsan', '+zhangsan', '@zhangsan'], path)
    rows = list(csv.reader(open(path, encoding='utf-8-sig')))[1:]
    assert [r[0] for r in rows] == ["'=zhangsan", "'-zhangsan", "'+zhangsan", "'@zhangsan"]


def test_export_csv_guards_leading_zero_and_long_numbers(tmp_path):
    """前导零与超 15 位数字也要保护：否则 000000 → 0、长号码变科学计数法"""
    path = str(tmp_path / 'd.csv')
    export_csv(['000000', '44030419950820123', '123456'], path)
    rows = list(csv.reader(open(path, encoding='utf-8-sig')))[1:]
    assert [r[0] for r in rows] == ["'000000", "'44030419950820123", '123456']


def test_export_csv_leaves_normal_passwords_untouched(tmp_path):
    """普通密码不能加引号，否则内容被污染"""
    path = str(tmp_path / 'd.csv')
    export_csv(['123456', 'zs123@', 'Zhangsan2024!'], path)
    rows = list(csv.reader(open(path, encoding='utf-8-sig')))[1:]
    assert [r[0] for r in rows] == ['123456', 'zs123@', 'Zhangsan2024!']


def test_export_txt_keeps_formula_prefix_raw(tmp_path):
    """TXT 面向爆破工具，绝不加单引号——否则密码内容错误"""
    path = str(tmp_path / 'd.txt')
    export_txt(['=zhangsan', '000000'], path)
    body = [l for l in open(path, encoding='utf-8').read().splitlines()
            if l and not l.startswith('#')]
    assert body == ['=zhangsan', '000000']


def test_format_size():
    assert format_size(512).endswith('B')
    assert format_size(2048).endswith('KB')
    assert format_size(2 * 1024 * 1024).endswith('MB')


# ------------------------------------------------------------------ 模板

def test_safe_template_name_blocks_traversal():
    """模板名不得把路径分隔符带进文件路径（否则写到 templates 目录外）"""
    assert '/' not in safe_template_name('../evil')
    assert '\\' not in safe_template_name('..\\evil')
    # 分隔符替换为下划线，前导点被剥离（避免生成隐藏文件）
    assert safe_template_name('../evil') == '_evil'
    assert safe_template_name('a/b') == 'a_b'
    assert safe_template_name('') == 'template'
    assert safe_template_name('...') == 'template'
    assert ':' not in safe_template_name('C:name')


def test_template_save_load_roundtrip():
    name = '_pytest_roundtrip'
    try:
        path = save_template(name, {'chinese_name': '张三'}, {'min_len': 8})
        assert os.path.realpath(path).startswith(os.path.realpath(TEMPLATE_DIR) + os.sep)

        data = load_template(name)
        assert data['info_data']['chinese_name'] == '张三'
        assert data['rules_config']['min_len'] == 8

        names = [t['name'] for t in list_templates()]
        assert name in names
    finally:
        delete_template(name)


def test_template_traversal_blocked_on_disk():
    """带 ../ 的名字必须落在 templates 目录内部"""
    name = '../_pytest_escape'
    try:
        path = save_template(name, {'x': '1'}, {})
        assert os.path.realpath(path).startswith(os.path.realpath(TEMPLATE_DIR) + os.sep)
        assert os.path.exists(path)
    finally:
        delete_template(name)


def test_template_missing_returns_none():
    assert load_template('_not_exist_12345') is None
