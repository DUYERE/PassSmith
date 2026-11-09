"""中文姓名处理模块 - 生成拼音全拼/首字母/分隔符变体/大小写/反向等"""

import pypinyin

from core.case_handler import case_variants, join_case_variants
from core.util import ascii_variants, has_chinese, is_ascii_password, load_config_file, normalize_text

# 常见复姓：不识别会把「欧阳」切成「欧/阳」，生成 ouynn 这类永远不会命中的垃圾变体
COMPOUND_SURNAMES = frozenset("""
欧阳 太史 端木 上官 司马 东方 独孤 南宫 万俟 闻人 夏侯 诸葛 尉迟 公羊 赫连 澹台
皇甫 宗政 濮阳 公冶 太叔 申屠 公孙 慕容 仲孙 钟离 长孙 宇文 司徒 鲜于 司空 闾丘
子车 亓官 司寇 巫马 公西 颛孙 壤驷 公良 漆雕 乐正 宰父 谷梁 拓跋 夹谷 轩辕 令狐
段干 百里 呼延 东郭 南门 羊舌 微生 梁丘 西门 第五 南荣 东里 仲长 即墨 达奚
""".split())

# 全拼参与大小写组合的分隔符：@ # 等只出现在邮箱/账号里，作为密码罕见
PINYIN_SEPARATORS = ('', '.', '_', '-')

# 多音字姓的内置兜底表：config/polyphone_surnames.txt 缺失时使用
# 映射值为「作为姓氏时的正确读音」（无声调），仅在单字姓时生效。
# 已按 pypinyin 无声调默认读音逐字复核：默认读音与姓氏读音相同的不收录（乐yuè/燕yān等无声调下相同）。
_BUILTIN_POLYPHONE = {
    '单': 'shan', '解': 'xie', '查': 'zha', '曾': 'zeng',
    '仇': 'qiu', '朴': 'piao', '区': 'ou', '乐': 'yue',
    '覃': 'qin', '召': 'shao', '句': 'gou', '秘': 'bi',
    '缪': 'miao', '都': 'du', '种': 'chong', '尉': 'yu',
    '阚': 'kan', '盖': 'ge',
    # 生僻但真实：隗姓读 wěi（pypinyin 默认 kuí）、员姓读 yùn（默认 yuán）
    '隗': 'wei', '员': 'yun',
}


def _load_polyphone_surnames():
    """内置表 + config/polyphone_surnames.txt 用户补充（格式：单字姓 空格 拼音）"""
    mapping = dict(_BUILTIN_POLYPHONE)
    for line in load_config_file('polyphone_surnames.txt'):
        parts = line.replace('\t', ' ').split()
        if len(parts) == 2 and len(parts[0]) == 1 and parts[1].isascii():
            mapping[parts[0]] = parts[1].lower()
    return mapping


POLYPHONE_SURNAMES = _load_polyphone_surnames()


def split_surname(name):
    """拆分姓与名，支持复姓；返回 (姓, 名)"""
    if len(name) >= 2 and name[:2] in COMPOUND_SURNAMES:
        return name[:2], name[2:]
    return name[:1], name[1:]


def to_pinyin(text):
    """中文转拼音，只保留 ASCII 结果

    pypinyin 对生僻字、emoji、符号会原样返回，直接 join 会把非 ASCII 字符带进密码，
    因此按音节过滤：能转的转，转不了的非 ASCII 片段丢弃。
    """
    if not text:
        return ''
    return ''.join(p for p in pypinyin.lazy_pinyin(text) if is_ascii_password(p))


def _pinyin_syllables(text):
    """按音节拆分并剔除 pypinyin 原样返回的非 ASCII 片段（生僻字/emoji）"""
    if not text:
        return []
    return [p for p in pypinyin.lazy_pinyin(text) if is_ascii_password(p)]


def _split_name(chinese_name):
    """解析中文姓名，返回 (全部音节, 姓拼音, 名音节)；无法解析返回 None"""
    chinese_name = normalize_text(chinese_name)
    if not chinese_name or not has_chinese(chinese_name):
        return None
    syllables = _pinyin_syllables(chinese_name)
    if not syllables:
        return None
    surname_chars, given_chars = split_surname(chinese_name)
    surname_pinyin = to_pinyin(surname_chars)
    given_syllables = _pinyin_syllables(given_chars)
    return syllables, surname_pinyin, given_syllables


def _assemble_name_variants(syllables, surname_pinyin, given_syllables, full_case=True):
    """按真实使用概率排序组装姓名变体（供主读音与多音字姓氏读音复用）

    顺序即优先级：字典前几百条是黄金位置，必须给最高频形态。
    全拼小写 → 首字母缩写 → 首字母大写全拼 → 其余大小写 → 分隔符 → 派生形态。
    """
    # 姓的首字母 token 数 = 总音节数 - 名音节数（复姓占前多个音节）
    surname_initials = [p[0] for p in syllables[:len(syllables) - len(given_syllables)]]

    full_forms = case_variants(syllables, '', full_case)          # zhangsan/Zhangsan/ZHANGSAN/ZhangSan
    initials_forms = case_variants([p[0] for p in syllables], '', full_case)  # zs/Zs/ZS/zS

    variants = []

    # 1) 全拼小写（最高频）：zhangsan
    variants.extend(full_forms[:1])

    # 2) 首字母缩写（第二高频）：zs / Zs / ZS / zS
    variants.extend(initials_forms)

    # 3) 全拼其余大小写形态：Zhangsan / ZHANGSAN / ZhangSan
    variants.extend(full_forms[1:])

    # 4) 分隔符形态：zhang.san / Zhang.san / …
    for sep in PINYIN_SEPARATORS[1:]:
        variants.extend(case_variants(syllables, sep, full_case))

    # 5) 姓全拼 + 名首字母：zhangs / Zhangs / ZHANGS
    if given_syllables:
        variants.extend(case_variants([surname_pinyin] + [p[0] for p in given_syllables], '', full_case))

    # 6) 仅姓：zhang / Zhang / ZHANG（姓名只有姓时与全拼重复，由去重处理）
    if surname_pinyin:
        variants.extend(case_variants([surname_pinyin], '', full_case))

    # 7) 名 + 姓（音节反向）：sanzhang / Sanzhang / SANZHANG / SanZhang
    #    字符级反转（nasgnahz）在真实密码中不存在，不再生成
    if given_syllables:
        variants.extend(case_variants(given_syllables + [surname_pinyin], '', full_case))

    # 8) 姓首字母 + 名全拼：zsan / Zsan / ZSAN（z + san 组合也有人用）
    if given_syllables:
        variants.extend(case_variants(surname_initials[:1] + given_syllables, '', full_case))

    # 9) 叠字：张三 → sansan / Sansan / SANSAN / SanSan（中文昵称高频形态）
    if len(syllables) >= 2:
        variants.extend(case_variants([syllables[-1]] * 2, '', full_case))

    return variants


def _surname_alt_reading(surname_chars, syllables):
    """多音字姓的正确读音：pypinyin 默认读音与姓氏读音不同时返回替换音节，否则 None"""
    if not surname_chars or len(surname_chars) != 1 or not syllables:
        return None
    alt = POLYPHONE_SURNAMES.get(surname_chars)
    if alt and syllables[0] != alt:
        return alt
    return None


def get_name_variants(chinese_name, full_case=True):
    """从中文姓名生成所有变体（绝不返回汉字，汉字密码在真实系统中不存在）

    full_case=True  时按 token 边界展开完整大小写组合（zs/Zs/ZS/zS、Zhang.san 等）；
    full_case=False 时每组只保留小写形态，用于关闭「大小写组合」规则压缩字典。
    """
    parsed = _split_name(chinese_name)
    if not parsed:
        # 纯英文名（或无法解析）
        return _english_name_variants(chinese_name, full_case)

    syllables, surname_pinyin, given_syllables = parsed
    surname_chars, _ = split_surname(normalize_text(chinese_name))

    variants = _assemble_name_variants(syllables, surname_pinyin, given_syllables, full_case)

    # 多音字姓：默认读音在真实世界里读错，正确读音的变体一个都不能少
    alt = _surname_alt_reading(surname_chars, syllables)
    if alt:
        variants.extend(_assemble_name_variants(
            [alt] + syllables[1:], alt, given_syllables, full_case))

    return ascii_variants(variants)


def get_name_combination_variants(chinese_name, full_case=True):
    """2/3 级组合使用的姓名形态代表

    组合器按「每类前 N 个变体」取材，而完整变体列表的前排全是全拼形态，
    zs / zhangs / sanzhang 等永远进不了组合。这里按形态组各取代表（约 10 个），
    保证组合阶段能覆盖所有命名习惯，同时控制组合规模。
    """
    parsed = _split_name(chinese_name)
    if not parsed:
        # 英文名：取前几个主形态
        en = _english_name_variants(chinese_name, full_case)
        return en[:4]

    syllables, surname_pinyin, given_syllables = parsed
    full_forms = case_variants(syllables, '', full_case)
    initials_forms = case_variants([p[0] for p in syllables], '', full_case)

    picks = []
    # 全拼小写（最高频）
    picks.extend(full_forms[:1])
    # 首字母缩写（第二高频，zS 属边缘写法不进组合）
    picks.extend(initials_forms[:3])
    # 多音字姓：正确读音全拼紧跟主形态——组合截断 [:8] 也能覆盖到
    surname_chars, _ = split_surname(normalize_text(chinese_name))
    alt = _surname_alt_reading(surname_chars, syllables)
    if alt:
        picks.extend(case_variants([alt] + syllables[1:], '', full_case)[:2])
    # 全拼首字母大写（第三高频）
    picks.extend(full_forms[1:2])
    # 分隔符形态各取 1 个代表
    picks.extend(case_variants(syllables, '.', full_case)[:1])
    picks.extend(case_variants(syllables, '_', full_case)[:1])
    if given_syllables:
        picks.extend(case_variants([surname_pinyin] + [p[0] for p in given_syllables], '', full_case)[:2])
        picks.extend(case_variants([surname_pinyin], '', full_case)[:1])
        picks.extend(case_variants(given_syllables + [surname_pinyin], '', full_case)[:1])

    return ascii_variants(picks)


def _english_name_variants(english_name, full_case=True):
    """处理英文姓名变体"""
    name = normalize_text(english_name)
    if not name:
        return []

    variants = [name]  # 原始形态（含空格写法）保留

    parts = name.split()
    if len(parts) > 1:
        # 词级展开：nanaouyang / Nanaouyang / NANAOUYANG / NanaOuyang + 分隔符形式
        variants.extend(join_case_variants(parts, PINYIN_SEPARATORS, full_case))
        variants.extend(case_variants([p[0] for p in parts], '', full_case))
    else:
        variants.extend(case_variants([name], '', full_case))

    return ascii_variants(variants)


def get_name_context(chinese_name, english_name=None, nickname=None, full_case=True):
    """
    生成姓名相关的上下文字典，用于自定义规则解析
    返回: {占位符名: [变体列表]}（只含 ASCII，绝不塞入原始汉字）
    """
    context = {}

    # 处理中文姓名
    chinese_name = normalize_text(chinese_name)
    if chinese_name and has_chinese(chinese_name):
        syllables = _pinyin_syllables(chinese_name)
        if syllables:
            surname_chars, given_chars = split_surname(chinese_name)
            surname_pinyin = to_pinyin(surname_chars)
            given_pinyin = to_pinyin(given_chars)
            context['姓名'] = case_variants(syllables, '', full_case)
            surname_forms = case_variants([surname_pinyin], '', full_case)
            alt = _surname_alt_reading(surname_chars, syllables)
            if alt:
                surname_forms = ascii_variants(surname_forms + [alt, alt[:1].upper() + alt[1:]])
            context['姓'] = surname_forms
            context['名'] = ascii_variants([
                given_pinyin,
                given_pinyin[:1].upper() + given_pinyin[1:] if given_pinyin else '',
            ])
            context['姓名首字母'] = case_variants([p[0] for p in syllables], '', full_case)
            if len(syllables) > 1:
                context['姓名变体'] = join_case_variants(syllables, ('.', '_'), full_case)

    # 处理英文名
    if english_name:
        en_variants = _english_name_variants(english_name, full_case)
        if en_variants:
            if '姓名' not in context:
                context['姓名'] = en_variants
            context.setdefault('英文名', en_variants)

    # 处理昵称
    nick = normalize_text(nickname)
    if nick:
        if has_chinese(nick):
            nick_syllables = _pinyin_syllables(nick)
            context['昵称'] = case_variants(nick_syllables, '', full_case)
        else:
            context['昵称'] = case_variants(nick.split() or [nick], '', full_case)

    return {k: v for k, v in context.items() if v}
