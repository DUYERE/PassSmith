"""用户输入格式容错测试：日期写法、邮箱残缺、列表分隔符、占位符展开上限"""

import pytest

from core.birthday_handler import get_birthday_variants
from core.email_handler import get_email_variants
from core.rule_parser import parse_custom_rule, PER_PLACEHOLDER_CAP
from core.util import split_list_text


# ------------------------------------------------------------------ 日期

CANONICAL = get_birthday_variants('1988-03-12')


@pytest.mark.parametrize('raw', [
    '1988-03-12', '1988/03/12', '1988.03.12', '19880312', '1988年3月12日', '88-03-12',
])
def test_date_formats_produce_identical_variants(raw):
    """各种日期写法必须产出同一套变体

    未归一化时 `1988.03.12`、`1988年3月12日` 会被原样当密码素材，
    产出永远不可能命中的垃圾组合。
    """
    assert get_birthday_variants(raw) == CANONICAL


@pytest.mark.parametrize('raw', ['1990-13-45', '乱写的', '1988年', '', '1988-03', 'abc-def-ghi'])
def test_invalid_date_returns_empty(raw):
    """无法识别或非法日期返回空，绝不返回原串当素材"""
    assert get_birthday_variants(raw) == []


def test_two_digit_year_expands_century():
    assert '20050312' in get_birthday_variants('05-03-12')
    assert '19950312' in get_birthday_variants('95-03-12')


def test_leap_day_valid():
    assert '20000229' in get_birthday_variants('2000-02-29')
    assert get_birthday_variants('2001-02-29') == []


# ------------------------------------------------------------------ 邮箱

def test_email_with_domain_but_no_at():
    """nana.qq.com 这类（漏了 @）取第一段作前缀，不能整串当密码素材"""
    assert get_email_variants('nana.qq.com')[:1] == ['nana']


def test_email_prefix_only():
    assert get_email_variants('nana')[:1] == ['nana']


def test_email_empty_prefix_returns_empty():
    assert get_email_variants('@qq.com') == []


def test_email_dotted_prefix_kept():
    assert get_email_variants('nana.ouyang@qq.com')[0] == 'nana.ouyang'


# ------------------------------------------------------------------ 列表分隔符

def test_split_list_text_default_keeps_space_in_password():
    """弱口令列表默认不按空格切分，含空格的密码不能被拆坏"""
    assert split_list_text('pass word,abc') == ['pass word', 'abc']


def test_split_list_text_allow_space_for_separators():
    """分隔符列表允许空格分隔（分隔符都是单字符符号）"""
    assert split_list_text('. _ - @ #', allow_space=True) == ['.', '_', '-', '@', '#']


def test_split_list_text_all_chinese_punctuation():
    assert split_list_text('a，b、c；d;e') == ['a', 'b', 'c', 'd', 'e']


# ------------------------------------------------------------------ 占位符上限

def test_placeholder_cap_allows_user_scale_lists():
    """上限过低会让用户手写的长列表后半段静默失效"""
    assert PER_PLACEHOLDER_CAP >= 100
    weak = [f'pw{i:03d}' for i in range(100)]
    context = {'弱口令': weak}
    out = parse_custom_rule('{弱口令}', context)
    assert len(out) == 100
    assert 'pw099' in out


def test_placeholder_cap_still_bounds_explosion():
    """上限仍然存在，防止超大列表把 UI 卡死"""
    weak = [f'pw{i:04d}' for i in range(500)]
    out = parse_custom_rule('{弱口令}', {'弱口令': weak})
    assert len(out) == PER_PLACEHOLDER_CAP
