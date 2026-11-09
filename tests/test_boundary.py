"""边界输入测试：异常/极端输入不得崩溃、不得产出非 ASCII、预估须与实际一致"""

import pytest

from core.combiner import PasswordGenerator


def _rules(**overrides):
    rules = {
        'max_depth': 3, 'min_len': 5, 'max_len': 20,
        'quick_rules': {}, 'custom_rules': '',
        'separators': ['.', '_', '-', '@', '#'],
    }
    rules.update(overrides)
    return rules


CASES = [
    ('空字典', {}),
    ('仅生日', {'birthday': '1990-01-15'}),
    ('仅手机', {'phone': '13812345678'}),
    ('仅身份证', {'idcard': '44030419950820123x'}),
    ('超长姓名', {'chinese_name': '欧阳娜娜娜娜娜娜娜娜'}),
    ('单字名', {'chinese_name': '张'}),
    ('英文姓名', {'english_name': 'John Smith'}),
    ('姓名含空格', {'chinese_name': '张 三'}),
    ('全角数字手机', {'phone': '１３８１２３４５６７８'}),
    ('非法生日', {'birthday': '1990-13-45'}),
    ('短身份证', {'idcard': '4403041995082012'}),
    ('纯符号输入', {'chinese_name': '！@#', 'phone': '---'}),
]


@pytest.mark.parametrize('tag,info', CASES, ids=[c[0] for c in CASES])
def test_boundary_inputs_are_safe(generator, tag, info):
    """所有边界输入：不抛异常、输出全 ASCII、预估与实际一致"""
    rules = _rules()
    out = list(generator.generate(info, rules))
    assert all(p.isascii() for p in out), f'{tag} 产出了非 ASCII'
    assert all(p == p.strip() for p in out), f'{tag} 产出了首尾带空白的密码'

    estimated, exact = generator.estimate_count(info, rules, detail=True)
    if exact:
        assert estimated == len(out), f'{tag} 预估与实际不一致'


def test_empty_info_generates_nothing(generator):
    """完全不填信息且关闭弱口令规则时不生成任何内容"""
    rules = _rules(quick_rules={'name_weak': False})
    assert list(generator.generate({}, rules)) == []
    assert generator.estimate_count({}, rules) == 0


def test_empty_info_still_outputs_pure_weak_passwords(generator):
    """不填个人信息也能导出纯弱口令字典——0 级通道不依赖任何个人信息

    用户手动加的弱口令（如 2580147369）必须能生成出来，否则「我加的词不生效」。
    """
    weak = ['password', 'qwerty', '2580147369', '123', '000000']
    rules = _rules(quick_rules={'name_weak': True}, weak_passwords=weak, min_len=8)
    out = list(generator.generate({}, rules))
    # qwerty(6) / 123(3) / 000000(6) 均被 min_len=8 过滤，剩下两条
    assert out == ['password', '2580147369']


def test_empty_info_estimate_matches_after_length_filter(generator):
    """纯弱口令场景的预估必须过完长度筛，不能直接返回弱口令总条数"""
    weak = ['password', 'qwerty', '2580147369', '123']
    rules = _rules(quick_rules={'name_weak': True}, weak_passwords=weak, min_len=8)
    actual = len(list(generator.generate({}, rules)))
    estimated, exact = generator.estimate_count({}, rules, detail=True)
    assert exact is True
    assert estimated == actual == 2


def test_weak_password_respects_complexity_filter(generator):
    """弱口令自身也要满足复杂度要求（标准策略下纯数字弱口令会被拦）"""
    rules = _rules(quick_rules={'name_weak': True},
                   weak_passwords=['123456', 'Password1!'], min_len=8,
                   require_digit=True, require_alpha=True, require_special=True)
    out = list(generator.generate({}, rules))
    assert out == ['Password1!']


def test_min_greater_than_max_yields_empty(generator):
    """上下限写反时输出为空（UI 已做联动，核心层保持诚实行为）"""
    out = list(generator.generate({'chinese_name': '张三'}, _rules(min_len=20, max_len=5)))
    assert out == []


def test_fullwidth_phone_normalized(generator):
    """全角数字必须归一化为半角，不能生成全角密码"""
    out = list(generator.generate({'phone': '１３８１２３４５６７８'}, _rules()))
    assert out
    assert any('13812345678' in p for p in out)


def test_invalid_date_ignored(generator):
    """1990-13-45 这类非法日期不能产出 19901345、199015 之类无效组合"""
    out = list(generator.generate({'birthday': '1990-13-45'}, _rules()))
    assert '19901345' not in out
    assert '199015' not in out


def test_very_long_name_bounded(generator):
    """超长姓名不能导致组合爆炸（变体数有上限）"""
    out = list(generator.generate({'chinese_name': '欧阳娜娜娜娜娜娜娜娜'}, _rules()))
    assert len(out) < 5000


def test_custom_rules_with_unknown_placeholder(generator):
    """未知占位符不能崩，最多是忽略"""
    rules = _rules(custom_rules='{姓名}{不存在的占位符}\n{生日年}{未知}')
    out = list(generator.generate({'chinese_name': '张三', 'birthday': '1990-01-15'}, rules))
    assert all(p.isascii() for p in out)
    assert any(p.startswith('zhangsan') for p in out)
