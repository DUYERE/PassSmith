"""姓名变体生成测试：大小写、缩写、复姓、多音字、叠字、ASCII 闸门"""

from core.name_handler import (
    get_name_variants,
    get_name_combination_variants,
    get_name_context,
    split_surname,
)


def test_basic_pinyin_variants():
    variants = get_name_variants('张三')
    for expected in ('zhangsan', 'Zhangsan', 'ZHANGSAN', 'ZhangSan', 'zhang.san', 'zhang_san'):
        assert expected in variants


def test_initial_case_combinations():
    """zs 四种写法都真实存在，必须全部生成"""
    variants = get_name_variants('张三')
    for expected in ('zs', 'Zs', 'ZS', 'zS'):
        assert expected in variants


def test_no_non_ascii():
    """绝不返回汉字/全角字符"""
    for name in ('张三', '欧阳娜娜', '李雷', '龘', '王😀明'):
        for variant in get_name_variants(name):
            assert variant.isascii(), f'{name} 产生了非 ASCII 变体：{variant}'


def test_compound_surname():
    """复姓不能被拆成「欧/阳」"""
    assert split_surname('欧阳娜娜') == ('欧阳', '娜娜')
    variants = get_name_variants('欧阳娜娜')
    assert 'ouyangnana' in variants
    assert 'oynn' in variants
    assert 'ouynn' not in variants


def test_compound_surname_reading():
    """pypinyin 内置复姓词典：尉迟/万俟/长孙/澹台 读音正确"""
    assert get_name_variants('尉迟恭')[0].startswith('yuchi')
    assert get_name_variants('万俟卨')[0].startswith('moqi')
    assert get_name_variants('长孙无忌')[0].startswith('zhangsun')
    assert get_name_variants('澹台灭明')[0].startswith('tantai')


def test_polyphone_surname():
    """多音字姓的正确读音与默认读音都要出现"""
    variants = get_name_variants('单婷婷')
    assert any(v.startswith('shantingting') for v in variants), '缺少正确读音 shan'
    assert any(v.startswith('dantingting') for v in variants), '缺少默认读音 dan'


def test_reduplicated_nickname():
    """叠字：张三 → sansan"""
    variants = get_name_variants('张三')
    assert 'sansan' in variants
    assert 'Sansan' in variants


def test_variant_order_priority():
    """顺序即优先级：全拼小写在最前，缩写紧随其后"""
    variants = get_name_variants('张三')
    assert variants[0] == 'zhangsan'
    assert variants.index('zs') < variants.index('Zhangsan')


def test_combination_picks():
    """组合代表名单覆盖各形态"""
    picks = get_name_combination_variants('张三')
    assert 'zhangsan' in picks
    assert any(p in ('zs', 'Zs', 'ZS') for p in picks)
    assert len(picks) <= 13


def test_context_placeholders():
    context = get_name_context('张三')
    assert 'zs' in context['姓名首字母'] and 'ZS' in context['姓名首字母']
    assert all(v.isascii() for variants in context.values() for v in variants)


def test_full_case_disabled():
    """关闭大小写组合时每组只留小写形态"""
    variants = get_name_variants('张三', full_case=False)
    assert 'zhangsan' in variants
    assert 'Zhangsan' not in variants
    assert 'ZS' not in variants


def test_english_name():
    variants = get_name_variants('Nana Ouyang')
    assert 'nanaouyang' in variants
    assert 'NanaOuyang' in variants
