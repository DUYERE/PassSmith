"""列表文本解析测试：中英文标点混用不得导致弱口令失效"""

from core.util import split_list_text


def test_english_comma():
    assert split_list_text('12345,1234,2580147369') == ['12345', '1234', '2580147369']


def test_chinese_comma():
    """中文输入法打出的全角逗号必须能分隔——这是用户实际踩过的坑"""
    assert split_list_text('12345，1234，2580147369') == ['12345', '1234', '2580147369']


def test_chinese_enumeration_comma():
    assert split_list_text('张三、李四、王五') == ['张三', '李四', '王五']


def test_mixed_punctuation():
    assert split_list_text('a，b,c、d;e；f') == ['a', 'b', 'c', 'd', 'e', 'f']


def test_newlines():
    assert split_list_text('a\nb\r\nc') == ['a', 'b', 'c']


def test_repeated_and_trailing_separators():
    assert split_list_text('a,,b，，c,') == ['a', 'b', 'c']


def test_empty_and_punctuation_only():
    assert split_list_text('') == []
    assert split_list_text('，，,,') == []


def test_strips_whitespace():
    assert split_list_text(' a , b ') == ['a', 'b']


def test_passwords_with_inner_symbols_kept_intact():
    """密码内部的 # @ . _ 不能被当成分隔符"""
    assert split_list_text('zs@123,zhang.san,abc#1') == ['zs@123', 'zhang.san', 'abc#1']


def test_fullwidth_password_list_regression():
    """回归：整串中文逗号列表曾被当成一条超长弱口令，导致全部失效"""
    text = '12345，1234，123，666，888，999，000，password，2580147369'
    items = split_list_text(text)
    assert len(items) == 9
    assert '2580147369' in items
    assert all('，' not in item for item in items)
