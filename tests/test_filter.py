"""筛选管道测试：ASCII 闸门、长度、复杂度、字符集模式"""

import pytest

from core.filter import filter_passwords, filter_by_charset, filter_by_complexity


def _run(passwords, **kwargs):
    return list(filter_passwords(iter(passwords), **kwargs))


def test_ascii_gate_blocks_chinese_and_emoji():
    """第一道闸门：汉字/emoji/换行一律拦截，任何路径都绕不过"""
    out = _run(['张三123', 'pass😀', 'ab\ncd', 'zhangsan123'], min_len=1)
    assert out == ['zhangsan123']


def test_length_filter():
    out = _run(['abcd', 'abcde', 'abcdefghij'], min_len=5, max_len=8)
    assert out == ['abcde']


def test_require_digit():
    out = _run(['abcdef', 'abc123', '123456'], require_digit=True, min_len=5)
    assert set(out) == {'abc123', '123456'}


def test_require_mixed_case():
    out = _run(['zhangsan', 'Zhangsan', 'ZHANGSAN', 'ZhangSan'], require_mixed_case=True, min_len=5)
    assert set(out) == {'Zhangsan', 'ZhangSan'}


def test_charset_alnum():
    out = _run(['zhang.san', 'zhangsan123', 'zs@123'], charset_mode='alnum', min_len=5)
    assert set(out) == {'zhangsan123'}


def test_charset_digit():
    out = _run(['19900115', 'zhangsan', '123456', 'abc123'], charset_mode='digit', min_len=4)
    assert set(out) == {'19900115', '123456'}


def test_combined_strategy():
    """标准策略：≥8 位 + 数字 + 字母 + 特殊字符 + 大小写混合"""
    candidates = [
        'Zhangsan123!',   # 合规
        'zhangsan123!',   # 缺大写
        'Zhangsan!',      # 缺数字
        'Zhangsan123',    # 缺特殊字符
        'ZHANGSAN123!',   # 缺小写
        'Zh1!',           # 太短
    ]
    out = _run(candidates, min_len=8, require_digit=True, require_alpha=True,
               require_special=True, require_mixed_case=True)
    assert out == ['Zhangsan123!']


def test_dedup_preserves_order():
    out = _run(['bbb', 'aaa', 'bbb', 'ccc'], min_len=3)
    assert out == ['bbb', 'aaa', 'ccc']


def test_char_first_then_complexity():
    """先字符集后复杂度：汉字条目不会被复杂度逻辑误判"""
    out = list(filter_by_complexity(filter_by_charset(['张三123', 'abc123']), require_digit=True))
    assert out == ['abc123']
