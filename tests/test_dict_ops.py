"""字典运算测试：合并去重、差集（排除已试密码）"""

from utils.dict_ops import read_passwords, merge_passwords, diff_passwords


def _write(tmp_path, name, lines):
    path = tmp_path / name
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return str(path)


def test_read_passwords_skips_comments_and_blanks(tmp_path):
    path = _write(tmp_path, 'a.txt', ['# 注释行', 'abc123', '', 'zs520!', '# 另一条注释'])
    assert list(read_passwords(path)) == ['abc123', 'zs520!']


def test_merge_dedup_preserves_order(tmp_path):
    f1 = _write(tmp_path, 'a.txt', ['aaa', 'bbb'])
    f2 = _write(tmp_path, 'b.txt', ['bbb', 'ccc'])
    assert merge_passwords([f1, f2]) == ['aaa', 'bbb', 'ccc']


def test_merge_single_file(tmp_path):
    f1 = _write(tmp_path, 'a.txt', ['x', 'y', 'x'])
    assert merge_passwords([f1]) == ['x', 'y']


def test_diff_removes_tried_passwords(tmp_path):
    base = _write(tmp_path, 'base.txt', ['123456', 'zhangsan123', 'zs520!', 'password', 'lilei2024'])
    tried1 = _write(tmp_path, 't1.txt', ['123456', 'other'])
    tried2 = _write(tmp_path, 't2.txt', ['password', 'zhangsan123'])

    result, base_count, exclude_count = diff_passwords(base, [tried1, tried2])
    assert result == ['zs520!', 'lilei2024']
    assert base_count == 5
    assert exclude_count == 4      # 123456 / other / password / zhangsan123


def test_diff_keeps_order_and_duplicates_collapsed(tmp_path):
    """基准里的重复行应折叠；顺序保持"""
    base = _write(tmp_path, 'base.txt', ['b', 'a', 'b', 'c'])
    result, _, _ = diff_passwords(base, [])
    assert result == ['b', 'a', 'c']


def test_diff_all_excluded(tmp_path):
    base = _write(tmp_path, 'base.txt', ['aaa', 'bbb'])
    tried = _write(tmp_path, 't.txt', ['aaa', 'bbb', 'ccc'])
    result, base_count, exclude_count = diff_passwords(base, [tried])
    assert result == []
    assert base_count == 2
    assert exclude_count == 3


def test_diff_ignores_comments_in_both_sides(tmp_path):
    base = _write(tmp_path, 'base.txt', ['# 头部注释', 'keep', 'drop'])
    tried = _write(tmp_path, 't.txt', ['# 注释', 'drop'])
    result, _, _ = diff_passwords(base, [tried])
    assert result == ['keep']
    assert '#' not in result


def test_diff_with_empty_exclude(tmp_path):
    base = _write(tmp_path, 'base.txt', ['a', 'b'])
    result, _, exclude_count = diff_passwords(base, [])
    assert result == ['a', 'b']
    assert exclude_count == 0
