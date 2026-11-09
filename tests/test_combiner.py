"""生成引擎测试：通道覆盖、策略筛选、预估一致性、保序稳定"""

import pytest

from core.combiner import PasswordGenerator, _spread, _numeric_weak, PREFIX_WEAK_LIMIT


def _generate(generator, info, **rule_overrides):
    rules = {
        'max_depth': 3,
        'min_len': 5,
        'max_len': 20,
        'quick_rules': {},
        'custom_rules': '',
        'separators': ['.', '_', '-', '@', '#'],
    }
    rules.update(rule_overrides)
    return list(generator.generate(info, rules))


def test_pure_weak_passwords_first(generator):
    """0 级通道：通用弱口令必须独立输出，且排在最前"""
    out = _generate(generator, {'chinese_name': '张三'})
    assert out[0] == '123456'
    assert '123456789' in out
    assert 'password' in out


def test_all_ascii(generator, basic_info):
    out = _generate(generator, basic_info)
    assert all(p.isascii() for p in out)


def test_size_stable_across_runs(generator, basic_info):
    """跨运行一致（set 会因哈希随机化导致顺序漂移）"""
    assert _generate(generator, basic_info) == _generate(generator, basic_info)


def test_reverse_concat_limited(generator):
    """反向拼接（弱口令+姓名）只保留少数前缀"""
    out = _generate(generator, {'chinese_name': '张三'}, min_len=4)
    reversed_hits = [p for p in out if p.endswith('zhangsan') and p != 'zhangsan']
    # 正向（zhangsan123）很多，反向的应显著更少
    forward_hits = [p for p in out if p.startswith('zhangsan')]
    assert len(reversed_hits) <= len(forward_hits) // max(1, PREFIX_WEAK_LIMIT)


def test_three_level_channels(generator):
    """3 级通道：姓名+弱口令+特殊字符、姓名+分隔符+弱口令"""
    out = _generate(generator, {'chinese_name': '张三'}, min_len=6)
    for expected in ('Zs123!', 'zhangsan123!', 'zs@123', 'zs#123'):
        assert expected in out, f'缺少 {expected}'


def test_birthday_no_invalid_date(generator, basic_info):
    """199015（1990 年 15 月）这类无效日期不能出现"""
    out = _generate(generator, basic_info)
    assert '199015' not in out


def test_phone_segment_not_standalone(generator):
    """号段（138）不该单独作为密码素材"""
    out = _generate(generator, {'chinese_name': '张三', 'phone': '13812345678'})
    assert 'zhangsan138' not in out


def test_idcard_x_case_pairs(generator):
    out = _generate(generator, {'idcard': '44030419950820123x'})
    assert any(p.endswith('123X') for p in out)
    assert any(p.endswith('123x') for p in out)


def test_standard_policy_zero_violation(generator, basic_info):
    """标准策略：输出必须全部满足 8位+数字+字母+特殊字符+大小写混合"""
    out = _generate(generator, basic_info, min_len=8, require_digit=True,
                    require_alpha=True, require_special=True, require_mixed_case=True)
    assert out
    for pwd in out:
        assert len(pwd) >= 8
        assert any(c.isdigit() for c in pwd)
        assert any(c.isupper() for c in pwd) and any(c.islower() for c in pwd)
        assert not pwd.isalnum()


def test_alnum_policy_no_special(generator, basic_info):
    out = _generate(generator, basic_info, charset_mode='alnum')
    assert out and all(p.isalnum() for p in out)


def test_digit_policy_all_numeric(generator, basic_info):
    out = _generate(generator, basic_info, charset_mode='digit', min_len=4, max_len=8)
    assert out and all(p.isdigit() for p in out)


def test_estimate_matches_generate(generator, basic_info):
    """小字典启用筛选时预估应为精确计数"""
    rules = {
        'max_depth': 3, 'min_len': 5, 'max_len': 20,
        'quick_rules': {}, 'custom_rules': '',
        'separators': ['.', '_', '-', '@', '#'],
        'require_mixed_case': True,
    }
    actual = len(list(generator.generate(basic_info, rules)))
    estimated, exact = generator.estimate_count(basic_info, rules, detail=True)
    assert exact is True
    assert estimated == actual


def test_custom_weak_passwords_enter_combinations(generator):
    """自定义弱口令必须能进复合组合（不能只取列表前几个）"""
    rules = {
        'max_depth': 3, 'min_len': 5, 'max_len': 20, 'quick_rules': {},
        'custom_rules': '', 'separators': ['.'],
        'weak_passwords': ['123456', '123321', '888888', 'woaini1314', 'qwerty2024'],
    }
    out = list(generator.generate({'chinese_name': '张三'}, rules))
    assert 'zhangsan888888!' in out
    assert 'zhangsanqwerty2024!' in out


def test_company_full_name_in_combinations(generator):
    """公司全名拼音要参与自动组合，不能只影响 {公司} 占位符"""
    out = _generate(generator, {'chinese_name': '张三', 'company': '腾讯科技'})
    assert 'tengxunkeji' in out
    assert any(p.startswith('tengxunkeji') and p != 'tengxunkeji' for p in out)


def test_spread_keeps_head_and_tail():
    items = list(range(20))
    picked = _spread(items, 6)
    assert len(picked) == 6
    assert picked[0] == 0          # 头部常用项必须保留
    assert picked[-1] > 10         # 尾部自定义项也要有代表


def test_numeric_weak_prefers_digits(generator):
    picked = _numeric_weak(generator.weak_passwords, 6)
    assert all(p.isdigit() for p in picked)


def test_numeric_weak_keeps_tail_custom_entry(generator):
    """数字型弱口令不足 12 个时，用户加在末尾的必须保留，不能被抽样漏掉"""
    weak = ['12345', '1234', '123', '666', '888', '999', '000', 'password',
            'qwerty', 'abc123', 'admin', 'root', 'test', 'iloveyou', 'welcome',
            'master', 'a123456', 'qq123456', 'woaini1314', '147258', '1qaz2wsx',
            '2580147369']
    picked = _numeric_weak(weak, 12)
    assert '2580147369' in picked, '末尾新增的数字弱口令被抽样丢弃'
    assert len(picked) == 12
    assert all(w in weak for w in picked)


def test_tail_custom_weak_enters_compound_channels(generator):
    """末尾弱口令必须能进「姓名+弱口令+特殊字符」复合通道（zs2580147369!）"""
    weak = ['12345', '1234', '123', '666', '888', '999', '000', 'password',
            'qwerty', 'abc123', 'admin', 'root', 'test', 'iloveyou', 'welcome',
            'master', 'a123456', 'qq123456', 'woaini1314', '147258', '1qaz2wsx',
            '2580147369']
    rules = {
        'max_depth': 3, 'min_len': 8, 'max_len': 20, 'quick_rules': {},
        'custom_rules': '', 'separators': ['.', '_', '-', '@', '#'],
        'weak_passwords': weak,
    }
    out = list(generator.generate({'chinese_name': '张三'}, rules))
    for expected in ('2580147369', 'zhangsan2580147369', 'zs2580147369',
                     'zs2580147369!', 'zhangsan2580147369@'):
        assert expected in out, f'缺少 {expected}'


def test_depth_controls_combination(generator, basic_info):
    """depth=1 时不应出现三元素组合"""
    out = _generate(generator, basic_info, max_depth=1, min_len=6)
    assert 'Zs123!' not in out
    assert 'zhangsan' in out
