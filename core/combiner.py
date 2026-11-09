"""组合生成引擎 - 核心密码生成逻辑

生成结果始终保序去重：字典文件中重复行只会增大体积，不会提高命中率，
因此去重为固定行为，配置中的 dedup 仅保留在筛选管道签名中以兼容。
"""

from datetime import datetime
from itertools import islice

from core.case_handler import case_variants, join_case_variants
from core.name_handler import (
    get_name_variants, get_name_combination_variants,
    _english_name_variants, _pinyin_syllables,
)
from core.birthday_handler import get_birthday_variants
from core.phone_handler import get_phone_variants
from core.idcard_handler import get_idcard_variants
from core.email_handler import get_email_variants
from core.id_handler import get_id_variants
from core.leet_handler import leet_speak_simple
from core.rule_parser import parse_custom_rules, get_all_context
from core.filter import filter_passwords
from core.util import (ascii_variants, has_chinese, is_ascii_password, is_mixed_case,
                       load_config_file, normalize_info, normalize_text, uniq_filter)

DEFAULT_SEPARATORS = ['.', '_', '-', '@', '#', '']
DEFAULT_KEYBOARD_PATTERNS = [
    'qwerty', 'asdf', 'zxcv', 'qazwsx', '1234qwer',
    'qweasd', '1qaz2wsx', '1qaz@wsx', '1q2w3e4r',
    '123qwe', 'qaz123', 'abcd1234', '!@#$%^', '!@#$%^&*', 'asdfgh',
]


# 反向拼接（弱口令+姓名）保留的弱口令个数：真实密码中「姓+后缀」远多于「后缀+姓」
PREFIX_WEAK_LIMIT = 3


def _spread(items, n):
    """抽样 n 个元素（保序、确定性）：前半取最常用项，后半在剩余项里均匀取

    弱口令列表默认项（123/123456/...）按频率排序在前，自定义项追加在后。
    纯均匀抽样会漏掉最高频的 123456，纯取前 N 又会把自定义项全挡住，
    因此头部保留一半、尾部均匀覆盖。
    """
    if n <= 0:
        return []
    if len(items) <= n:
        return list(items)
    head = n // 2
    picked = list(items[:head])
    rest = items[head:]
    tail_n = n - head
    step = len(rest) / tail_n
    picked.extend(rest[int(i * step)] for i in range(tail_n))
    return picked


def _numeric_weak(weak, n=12):
    """姓名复合形态优先用数字型弱口令

    `zhangsan123!` / `zs520!` 是真实高频形态，`zhangsanpassword!` 几乎不存在。

    数字型不足 n 个时必须保留全部数字型、再用非数字型补足名额。
    不能整体回退 _spread 抽样——否则用户手加在列表末尾的数字弱口令
    （如 2580147369）会被抽样漏掉，表现为「我加的词不生效」。
    """
    nums = [w for w in weak if w.isdigit()]
    if len(nums) >= n:
        return nums[:n]
    if not nums:
        return _spread(weak, n)

    rest = [w for w in weak if not w.isdigit()]
    need = n - len(nums)
    return nums + (_spread(rest, need) if need > 0 else [])


def _text_variants(text, extra=(), full_case=True):
    """通用文本变体：中文只转拼音（绝不保留汉字），按音节做大小写组合 + 叠字形态"""
    text = normalize_text(text)
    if not text:
        return []
    if has_chinese(text):
        syllables = _pinyin_syllables(text)
        variants = join_case_variants(syllables, ('',), full_case)
        # 叠字：旺财 → caicai / Caicai / CAICAI / CaiCai（中文昵称高频形态）
        if len(syllables) >= 2:
            variants.extend(case_variants([syllables[-1]] * 2, '', full_case))
    else:
        variants = case_variants(text.split() or [text], '', full_case)
    variants.extend(extra)
    return ascii_variants(variants)


class PasswordGenerator:
    """密码字典生成器"""

    def __init__(self):
        self.weak_passwords = load_config_file('weak_passwords.txt')
        self.prefixes = load_config_file('prefixes.txt')
        self.suffixes = self._with_year_suffixes(load_config_file('suffixes.txt'))
        self.separators = load_config_file('separators.txt', DEFAULT_SEPARATORS)
        self.keyboard_patterns = load_config_file('keyboard_patterns.txt', DEFAULT_KEYBOARD_PATTERNS)
        # 上一次生成中「规则里写了但没填对应信息」的占位符（供界面提示）
        self.last_missing_placeholders = set()

    @staticmethod
    def _with_year_suffixes(suffixes):
        """动态追加近期年份后缀：2026 / @2026 / 2026!

        「姓名+近期年份」是当前最常见的密码尾缀模式，写死在配置里会逐年过时。
        """
        year = datetime.now().year
        extra = []
        for y in (year - 1, year, year + 1):
            extra.extend([str(y), f'@{y}', f'{y}!'])
        return uniq_filter(list(suffixes) + extra)

    # ---------------------------------------------------------------- 生成

    def generate(self, info_data, rules_config):
        """主生成方法，返回保序去重并筛选后的密码生成器"""
        info_data = normalize_info(info_data)
        elements, name_picks = self._build_elements(info_data, rules_config)

        # 注意：elements 为空不能直接返回——0 级纯弱口令不依赖任何个人信息，
        # 用户可能只想导出一份通用弱口令字典（「姓名+弱口令」规则开启即可）。
        # 组合阶段遍历空 elements 自然跳过，不会产生额外输出。

        min_len = rules_config.get('min_len', 5)
        max_len = rules_config.get('max_len', 20)
        require_digit = rules_config.get('require_digit', False)
        require_alpha = rules_config.get('require_alpha', False)
        require_special = rules_config.get('require_special', False)
        # 目标站点策略：大小写混合要求 + 字符集白名单（any/alnum/digit）
        require_mixed_case = rules_config.get('require_mixed_case', False)
        charset_mode = rules_config.get('charset_mode', 'any')

        raw = self._generate_raw(elements, rules_config, info_data, name_picks)
        return filter_passwords(
            raw, min_len, max_len,
            require_digit, require_alpha, require_special,
            require_mixed_case, charset_mode,
            dedup=False,  # 组合器内部已保序去重
        )

    def _build_elements(self, info_data, rules_config=None):
        """构建各类信息变体元素字典（保序，主变体在前）"""
        quick_rules = (rules_config or {}).get('quick_rules', {})
        full_case = quick_rules.get('case_variants', True)

        elements = {}

        name_variants = []
        if info_data.get('chinese_name'):
            name_variants.extend(get_name_variants(info_data['chinese_name'], full_case))
        if info_data.get('english_name'):
            name_variants.extend(_english_name_variants(info_data['english_name'], full_case))
        if info_data.get('nickname'):
            name_variants.extend(_text_variants(info_data['nickname'], full_case=full_case))
        if name_variants:
            elements['name'] = uniq_filter(name_variants)

        if info_data.get('birthday'):
            variants = get_birthday_variants(info_data['birthday'])
            if variants:
                elements['birthday'] = variants

        if info_data.get('partner_birthday'):
            variants = get_birthday_variants(info_data['partner_birthday'])
            if variants:
                elements['partner_birthday'] = variants

        if info_data.get('phone'):
            variants = get_phone_variants(info_data['phone'])
            if variants:
                elements['phone'] = variants

        if info_data.get('idcard'):
            variants = get_idcard_variants(info_data['idcard'])
            if variants:
                elements['idcard'] = variants

        if info_data.get('email'):
            variants = get_email_variants(info_data['email'])
            if variants:
                elements['email'] = variants

        if info_data.get('work_id'):
            variants = get_id_variants(info_data['work_id'])
            if variants:
                elements['work_id'] = variants

        if info_data.get('student_id'):
            variants = get_id_variants(info_data['student_id'])
            if variants:
                elements['student_id'] = variants

        if info_data.get('qq'):
            qq = info_data['qq'].strip()
            variants = [qq]
            if len(qq) >= 4:
                variants.append(qq[-4:])
            if len(qq) >= 6:
                variants.append(qq[-6:])
            elements['qq'] = uniq_filter(variants)

        if info_data.get('wechat'):
            wechat = info_data['wechat'].strip()
            elements['wechat'] = uniq_filter([wechat, wechat.lower()])

        if info_data.get('company_abbr'):
            abbr = info_data['company_abbr'].strip()
            elements['company'] = uniq_filter([abbr, abbr.lower(), abbr.upper()])

        # 公司/学校全名：tengxun2024、Tencent@123 是常见素材，
        # 此前只用了缩写，全名填了等于不生效（只影响自定义规则 {公司}）
        if info_data.get('company'):
            company = info_data['company'].strip()
            if has_chinese(company):
                elements['company_name'] = case_variants(_pinyin_syllables(company), '', full_case)
            else:
                elements['company_name'] = case_variants(company.split() or [company], '', full_case)

        if info_data.get('username'):
            uid = info_data['username'].strip()
            elements['username'] = uniq_filter([uid, uid.lower(), uid.capitalize()])

        variants = _text_variants(info_data.get('pet_name', ''), full_case=full_case)
        if variants:
            elements['pet'] = variants

        if info_data.get('partner_name'):
            partner = info_data['partner_name'].strip()
            if has_chinese(partner):
                elements['partner_name'] = get_name_variants(partner, full_case)
            else:
                elements['partner_name'] = _english_name_variants(partner, full_case)

        variants = _text_variants(info_data.get('father_name', ''), full_case=full_case)
        if variants:
            elements['father'] = variants

        variants = _text_variants(info_data.get('mother_name', ''), full_case=full_case)
        if variants:
            elements['mother'] = variants

        # 城市（中文只保留拼音变体，避免中文密码噪音）
        if info_data.get('city'):
            city = info_data['city'].strip()
            if has_chinese(city):
                elements['city'] = case_variants(_pinyin_syllables(city), '', full_case)
            else:
                elements['city'] = case_variants(city.split() or [city], '', full_case)

        # 兜底闸门：所有类别的变体一律只保留 ASCII
        # 汉字/全角/emoji 变体在真实系统中不可能成为密码，留着只会污染字典、拉低命中率
        clean = {}
        for key, variants in elements.items():
            kept = ascii_variants(variants)
            if kept:
                clean[key] = kept

        # 2/3 级组合用的姓名形态代表，单独返回（与元素字典解耦）
        # 名单来源优先级：中文姓名 > 英文名 > 昵称——与 elements['name'] 的构成一致
        name_picks = []
        if 'name' in clean:
            name_source = (info_data.get('chinese_name')
                           or info_data.get('english_name')
                           or info_data.get('nickname') or '')
            name_picks = (get_name_combination_variants(name_source, full_case)
                          or clean['name'][:5])

        # 策略感知：要求大小写混合时，纯小写/纯大写形态在出口必被过滤，
        # 提前剔除可把组合预算让给有效形态（同配置下有效条目约翻倍）
        if (rules_config or {}).get('require_mixed_case'):
            mixed = [v for v in clean.get('name', []) if is_mixed_case(v)]
            if mixed:
                clean['name'] = mixed
                name_picks = [v for v in name_picks if is_mixed_case(v)] or mixed[:5]

        return clean, name_picks

    def _generate_raw(self, elements, rules_config, info_data, name_picks):
        """生成原始密码流（生成器，内部保序去重）

        name_picks: 组合阶段使用的姓名形态代表（含全拼/大小写/缩写/反向各形态），
        直接用 elements['name'] 前 N 个只会拿到全拼，大小写组合全部进不了组合
        """

        quick_rules = rules_config.get('quick_rules', {})
        rule = lambda key, default=False: quick_rules.get(key, default)  # noqa: E731
        rule_name_weak = rule('name_weak', True)
        rule_name_birthday = rule('name_birthday', True)
        rule_phone = rule('phone_variants', True)
        rule_idcard = rule('idcard_variants', True)
        rule_name_special = rule('name_special', True)
        rule_name_initial_num = rule('name_initial_num')
        rule_email_prefix = rule('email_prefix')
        rule_work_student_id = rule('work_student_id')
        rule_leet = rule('leet_speak')
        rule_keyboard = rule('keyboard_pattern')

        weak = rules_config.get('weak_passwords') or self.weak_passwords
        seps = rules_config.get('separators') or self.separators
        max_depth = rules_config.get('max_depth', 3)
        custom_rules = rules_config.get('custom_rules', '')

        categories = list(elements.keys())
        # 用 dict 模拟保序 set：set 迭代顺序受字符串哈希随机化影响，
        # 跨进程不稳定，会让 leet/键盘模式作用的「前 200 条」每次运行都不同
        generated = {}

        def emit(pwd):
            """输出一条密码：非 ASCII/含空白字符一律丢弃；已存在时返回 None"""
            if not is_ascii_password(pwd):
                return None
            if pwd not in generated:
                generated[pwd] = True
                return pwd
            return None

        # === 0级：纯弱口令 ===
        # 123456 / password / 888888 这类通用弱口令命中率最高，且不依赖任何个人信息。
        # 此前 weak 只作为组合原料、从未单独输出，等于把最容易命中的部分丢了。
        if rule_name_weak:
            for w in weak:
                if emit(w):
                    yield w

        # === 1级：单元素衍生 ===
        for category, variants in elements.items():
            for v in variants:
                if emit(v):
                    yield v

                # 姓名变体 + 弱口令：正向（name+weak）是真实高频形态
                if rule_name_weak and category == 'name':
                    for w in weak:
                        if emit(v + w):
                            yield v + w
                    # 反向（weak+name，如 123zhangsan）真实频率远低于正向，
                    # 只保留最常用的几个，否则会占满字典前半段的黄金位置
                    for w in weak[:PREFIX_WEAK_LIMIT]:
                        if emit(w + v):
                            yield w + v

                # 姓名变体 + 特殊字符前/后缀
                if rule_name_special and category == 'name':
                    for suffix in self.suffixes:
                        if emit(v + suffix):
                            yield v + suffix
                    for prefix in self.prefixes:
                        if emit(prefix + v):
                            yield prefix + v

        # 其余类别的单元素 + 弱口令
        if rule_name_weak:
            for category, variants in elements.items():
                if category == 'name':
                    continue
                for v in variants[:8]:
                    for w in _spread(weak, 10):
                        if emit(v + w):
                            yield v + w

        # === 2级：双元素组合 ===
        if max_depth >= 2:
            # 姓名首字母 + 数字类信息
            if rule_name_initial_num and 'name' in elements:
                short_names = [v for v in elements['name'] if len(v) <= 4][:5]
                for nv in short_names:
                    for cat2 in ('birthday', 'phone', 'idcard', 'qq', 'work_id', 'student_id'):
                        for v2 in elements.get(cat2, [])[:8]:
                            if emit(nv + v2):
                                yield nv + v2
                            for sep in seps[:5]:
                                if sep and emit(nv + sep + v2):
                                    yield nv + sep + v2

            # 姓名 + 生日
            if rule_name_birthday and 'name' in elements and 'birthday' in elements:
                for nv in name_picks[:8]:
                    for bv in elements['birthday'][:8]:
                        if emit(nv + bv):
                            yield nv + bv
                        for sep in seps[:4]:
                            if sep and emit(nv + sep + bv):
                                yield nv + sep + bv

            # 手机号衍生
            if rule_phone and 'phone' in elements:
                for pv in elements['phone'][:5]:
                    for w in _spread(weak, 8):
                        if emit(pv + w):
                            yield pv + w
                        if emit(w + pv):
                            yield w + pv
                    if 'name' in elements:
                        for nv in name_picks[:5]:
                            if emit(nv + pv):
                                yield nv + pv

            # 身份证衍生
            if rule_idcard and 'idcard' in elements:
                for iv in elements['idcard'][:5]:
                    for w in _spread(weak, 5):
                        if emit(iv + w):
                            yield iv + w
                    if 'name' in elements:
                        for nv in name_picks[:5]:
                            if emit(nv + iv):
                                yield nv + iv

            # 邮箱前缀衍生
            if rule_email_prefix and 'email' in elements:
                for ev in elements['email'][:5]:
                    for w in _spread(weak, 8):
                        if emit(ev + w):
                            yield ev + w
                    for suffix in self.suffixes:
                        if emit(ev + suffix):
                            yield ev + suffix

            # 工号/学号衍生
            if rule_work_student_id:
                for cat in ('work_id', 'student_id'):
                    for iv in elements.get(cat, [])[:3]:
                        for w in _spread(weak, 5):
                            if emit(iv + w):
                                yield iv + w

            # 通用双元素组合（不同类别，限制变体数防膨胀）
            # 姓名类别用形态代表名单，其余类别取前 5 个主变体
            for i, cat1 in enumerate(categories):
                for j, cat2 in enumerate(categories):
                    if i == j:
                        continue
                    v1_list = name_picks if cat1 == 'name' else elements[cat1][:5]
                    v2_list = name_picks if cat2 == 'name' else elements[cat2][:5]
                    for v1 in v1_list:
                        for v2 in v2_list:
                            if emit(v1 + v2):
                                yield v1 + v2

        # === 3级：三元素组合 ===
        if max_depth >= 3:
            # 姓名 + 弱口令 + 特殊字符：Zs123!、zhangsan@2024、zs520#
            # 这是国内密码最高频的复合尾缀形态，此前完全没有生成通道
            if rule_name_weak and rule_name_special and 'name' in elements:
                for nv in name_picks[:6]:
                    for w in _numeric_weak(weak, 12):
                        for suffix in self.suffixes[:8]:
                            if emit(nv + w + suffix):
                                yield nv + w + suffix

            # 姓名 + 分隔符/特殊字符 + 弱口令：zs@123、zs#123、zhang.san#123
            if rule_name_weak and 'name' in elements:
                for nv in name_picks[:6]:
                    for sep in [s for s in seps if s][:5]:
                        for w in _numeric_weak(weak, 12):
                            if emit(nv + sep + w):
                                yield nv + sep + w

            # 姓名+生日+弱口令/后缀
            if 'name' in elements and 'birthday' in elements:
                for nv in name_picks[:5]:
                    for bv in elements['birthday'][:5]:
                        for w in _spread(weak, 8):
                            if emit(nv + bv + w):
                                yield nv + bv + w
                        for suffix in self.suffixes:
                            if emit(nv + bv + suffix):
                                yield nv + bv + suffix

            # 姓名+手机+弱口令
            if 'name' in elements and 'phone' in elements:
                for nv in name_picks[:3]:
                    for pv in elements['phone'][:3]:
                        for w in _spread(weak, 5):
                            if emit(nv + pv + w):
                                yield nv + pv + w

            # 通用三元素组合
            top = min(len(categories), 4)
            for i in range(top):
                for j in range(top):
                    for k in range(top):
                        if i == j or j == k or i == k:
                            continue
                        v1_list = name_picks[:4] if categories[i] == 'name' else elements[categories[i]][:3]
                        v2_list = name_picks[:4] if categories[j] == 'name' else elements[categories[j]][:3]
                        v3_list = name_picks[:3] if categories[k] == 'name' else elements[categories[k]][:2]
                        for v1 in v1_list:
                            for v2 in v2_list:
                                for v3 in v3_list:
                                    if emit(v1 + v2 + v3):
                                        yield v1 + v2 + v3

        # === Leet Speak（对已有结果的前 200 条做变体）===
        if rule_leet:
            # 只取前 200 个键：list(generated)[:200] 会先物化几十万个键，
            # 而直接 islice(generated, 200) 又会在循环内的 emit() 写字典时
            # 触发「dictionary changed size during iteration」
            for pwd in list(islice(generated, 200)):
                if any(c.isalpha() for c in pwd):
                    for lv in leet_speak_simple(pwd)[1:]:
                        if emit(lv):
                            yield lv

        # === 键盘模式 ===
        if rule_keyboard:
            for pattern in self.keyboard_patterns:
                if emit(pattern):
                    yield pattern

        # === 自定义规则 ===
        self.last_missing_placeholders = set()
        if custom_rules and custom_rules.strip():
            context = get_all_context(info_data, rule('case_variants', True))
            context['弱口令'] = weak
            context['前缀'] = self.prefixes
            context['后缀'] = self.suffixes
            context['分隔符'] = seps

            missing = set()
            for pwd in parse_custom_rules(custom_rules, context, missing):
                if emit(pwd):
                    yield pwd
            self.last_missing_placeholders = missing

    # ---------------------------------------------------------------- 预估

    def estimate_count(self, info_data, rules_config, detail=False):
        """估算生成数量

        detail=True 时返回 (count, exact)，exact 表示该数字是否为精确计数
        （小字典启用筛选时会直接生成计数，误差为 0）。
        """
        def out(count, exact=True):
            return (count, exact) if detail else count

        info_data = normalize_info(info_data)
        elements, name_picks = self._build_elements(info_data, rules_config)
        if not elements:
            # 无个人信息时仍会输出 0 级纯弱口令（若「姓名+弱口令」规则开启）。
            # 弱口令自身也要过长度/复杂度筛选，故直接精确计数（规模极小）
            if not (rules_config.get('quick_rules', {}).get('name_weak', True)):
                return out(0, True)
            return out(sum(1 for _ in self.generate(info_data, rules_config)), True)

        n_name_picks = len(name_picks)

        # 纯数字策略（PIN）：姓名/拼音类变体在出口全部被拦，只有号码类元素的
        # 数字变体（生日/手机/身份证/QQ/工号）能通过。走专用估算，否则误差可达数百倍
        if rules_config.get('charset_mode', 'any') == 'digit':
            numeric = sum(len([v for v in variants if v.isdigit()])
                          for cat, variants in elements.items() if cat != 'name')
            approx = max(1, int(numeric * 2.5 * ESTIMATE_CALIBRATION))
            if approx <= EXACT_COUNT_LIMIT:
                return out(sum(1 for _ in self.generate(info_data, rules_config)), True)
            return out(approx, False)

        quick_rules = rules_config.get('quick_rules', {})
        rule = lambda key, default=False: quick_rules.get(key, default)  # noqa: E731
        weak = rules_config.get('weak_passwords') or self.weak_passwords
        seps = rules_config.get('separators') or self.separators
        max_depth = rules_config.get('max_depth', 3)
        n_weak = len(weak)
        n_prefix, n_suffix = len(self.prefixes), len(self.suffixes)

        total = 0

        # 0级：纯弱口令
        if rule('name_weak', True):
            total += n_weak

        # 1级
        for cat, variants in elements.items():
            n = len(variants)
            total += n
            if cat == 'name':
                if rule('name_weak', True):
                    total += n * n_weak + n * min(n_weak, PREFIX_WEAK_LIMIT)
                if rule('name_special', True):
                    total += n * (n_prefix + n_suffix)
            elif rule('name_weak', True):
                total += min(n, 8) * min(n_weak, 10)

        # 2级
        if max_depth >= 2:
            if rule('name_initial_num') and 'name' in elements:
                short = len([v for v in elements['name'] if len(v) <= 4][:5])
                total += short * sum(min(len(elements[c]), 8) for c in
                                     ('birthday', 'phone', 'idcard', 'qq', 'work_id', 'student_id')
                                     if c in elements) * (1 + min(5, len(seps)))

            if rule('name_birthday', True) and 'name' in elements and 'birthday' in elements:
                total += min(n_name_picks, 8) * min(len(elements['birthday']), 8) * (1 + min(4, len(seps)))

            if rule('phone_variants', True) and 'phone' in elements:
                n = min(len(elements['phone']), 5)
                total += n * (min(n_weak, 8) * 2 + min(n_name_picks, 5))

            if rule('idcard_variants', True) and 'idcard' in elements:
                n = min(len(elements['idcard']), 5)
                total += n * (min(n_weak, 5) + min(n_name_picks, 5))

            if rule('email_prefix') and 'email' in elements:
                n = min(len(elements['email']), 5)
                total += n * (min(n_weak, 8) + n_suffix)

            if rule('work_student_id'):
                total += sum(min(len(elements[c]), 3) * min(n_weak, 5)
                             for c in ('work_id', 'student_id') if c in elements)

            cats = list(elements.keys())
            for i, c1 in enumerate(cats):
                for j, c2 in enumerate(cats):
                    if i != j:
                        n1 = n_name_picks if c1 == 'name' else min(len(elements[c1]), 5)
                        n2 = n_name_picks if c2 == 'name' else min(len(elements[c2]), 5)
                        total += n1 * n2

        # 3级
        if max_depth >= 3:
            if rule('name_weak', True) and rule('name_special', True) and 'name' in elements:
                total += min(n_name_picks, 6) * len(_numeric_weak(weak, 12)) * min(n_suffix, 8)
            if rule('name_weak', True) and 'name' in elements:
                total += min(n_name_picks, 6) * min(len([s for s in seps if s]), 5) * min(n_weak, 12)

            if 'name' in elements and 'birthday' in elements:
                total += min(n_name_picks, 5) * min(len(elements['birthday']), 5) * (min(n_weak, 8) + n_suffix)
            if 'name' in elements and 'phone' in elements:
                total += min(n_name_picks, 3) * min(len(elements['phone']), 3) * min(n_weak, 5)

            cats = list(elements.keys())
            top = min(len(cats), 4)
            for i in range(top):
                for j in range(top):
                    for k in range(top):
                        if i == j or j == k or i == k:
                            continue
                        n1 = min(n_name_picks, 4) if cats[i] == 'name' else min(len(elements[cats[i]]), 3)
                        n2 = min(n_name_picks, 4) if cats[j] == 'name' else min(len(elements[cats[j]]), 3)
                        n3 = min(n_name_picks, 3) if cats[k] == 'name' else min(len(elements[cats[k]]), 2)
                        total += n1 * n2 * n3

        # 变换类规则只在已有结果前 200 条上展开，增量有限
        if rule('leet_speak'):
            total += 200
        if rule('keyboard_pattern'):
            total += len(self.keyboard_patterns)

        # 自定义规则：按占位符上下文长度估算（每占位符封顶，防爆炸）
        custom = rules_config.get('custom_rules', '')
        if custom and custom.strip():
            try:
                context = get_all_context(info_data, rule('case_variants', True))
                context['弱口令'] = weak
                context['前缀'] = self.prefixes
                context['后缀'] = self.suffixes
                context['分隔符'] = seps
                total += _estimate_custom_rules(custom, context)
            except Exception:
                pass

        # 实测校准：纯算术预估不含去重建模，7 组画像的 est/act 比值在 1.08~1.25
        # （字段越多交叉重叠越多）。取近似中位 0.85：
        # 大字典高估 ≤6%（50 万警告线仍然安全），小字典低估不影响警告逻辑
        calibrated = max(1, int(total * ESTIMATE_CALIBRATION))

        # 启用筛选时，纯算术无法建模过滤比例（标准策略实测偏差可达 4 倍）。
        # 生成速度极快（1 万条 ~10ms），小字典直接精确计数，消灭误导性预估值
        if _has_active_filter(rules_config) and calibrated <= EXACT_COUNT_LIMIT:
            return out(sum(1 for _ in self.generate(info_data, rules_config)), True)
        return out(calibrated, False)


# 预估校准因子：总计数 × 0.85 ≈ 实际生成数
ESTIMATE_CALIBRATION = 0.85

# 低于该规模时，启用筛选的预估改为精确计数（生成成本可忽略，结果零误差）
EXACT_COUNT_LIMIT = 50000


def _has_active_filter(rules_config):
    """是否启用了会影响最终数量的筛选条件"""
    return bool(
        rules_config.get('require_digit')
        or rules_config.get('require_alpha')
        or rules_config.get('require_special')
        or rules_config.get('require_mixed_case')
        or rules_config.get('charset_mode', 'any') != 'any'
        or rules_config.get('min_len', 5) > 4
        or rules_config.get('max_len', 20) < 20
    )


def _estimate_custom_rules(rules_text, context, per_placeholder_cap=None, per_line_cap=20000):
    """估算自定义规则展开数量（cap 默认与解析器的 PER_PLACEHOLDER_CAP 保持一致）"""
    from core import rule_parser
    from core.rule_parser import parse_rule_tokens

    if per_placeholder_cap is None:
        per_placeholder_cap = rule_parser.PER_PLACEHOLDER_CAP

    total = 0
    for line in rules_text.strip().split('\n'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        combos = 1
        for key in parse_rule_tokens(line):
            n = len(context.get(key) or [])
            if n:
                combos *= min(n, per_placeholder_cap)
            if combos >= per_line_cap:
                combos = per_line_cap
                break
        total += combos
    return total
