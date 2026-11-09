"""自定义规则解析器 - 解析 {姓名}{生日年} 等模板语法"""

import re
from itertools import product

# 单个占位符最多展开的变体数：防止 {弱口令} 等大列表导致组合爆炸卡死 UI。
# 取 128 而非更小的值——用户手写的弱口令/后缀列表常在 30~100 条，
# 上限过低会让后半段静默失效（「我加的词不生效」），这是比爆量更难排查的问题。
# 128 × 4 形态 × 5 分隔符 ≈ 2560 条，仍在可接受范围。
PER_PLACEHOLDER_CAP = 128
PLACEHOLDER_RE = re.compile(r'\{([^{}]+)\}')


def parse_rule_tokens(rule_str):
    """提取规则中的占位符名列表（按出现顺序，去重）"""
    seen = []
    for m in PLACEHOLDER_RE.finditer(rule_str):
        key = m.group(1).strip()
        if key not in seen:
            seen.append(key)
    return seen


def parse_custom_rule(rule_str, context):
    """
    解析自定义规则，如 {姓名}{生日年}
    context: 包含所有信息变体的字典 {占位符名: [变体列表]}
    返回：该规则生成的所有密码列表（每个占位符变体数封顶，防膨胀）
    """
    if not rule_str or not rule_str.strip():
        return []

    rule_str = rule_str.strip()

    parts = []
    last_end = 0
    for m in PLACEHOLDER_RE.finditer(rule_str):
        # 占位符之前的字面量
        if m.start() > last_end:
            parts.append([rule_str[last_end:m.start()]])
        key = m.group(1).strip()
        variants = context.get(key) or []
        parts.append(list(variants[:PER_PLACEHOLDER_CAP]))
        last_end = m.end()
    if last_end < len(rule_str):
        parts.append([rule_str[last_end:]])

    if not parts:
        return []

    return [''.join(combo) for combo in product(*parts)]


def parse_custom_rules(rules_text, context, missing=None):
    """
    解析多条自定义规则（每行一条，# 开头为注释）
    missing: 可选 set，收集规则里出现但 context 中不存在的占位符名

    缺失占位符会让所在行展开为空（product 遇到空列表直接得空结果），
    用户表现为「规则写了但一条都没生成」。把名字收集出来交给 UI 提示，
    否则这是最难自查的一类问题。
    返回：生成器，yield每条密码
    """
    if not rules_text or not rules_text.strip():
        return

    for line in rules_text.strip().split('\n'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if missing is not None:
            missing.update(key for key in parse_rule_tokens(line) if key not in context)
        yield from parse_custom_rule(line, context)


def get_all_context(info_data, full_case=True):
    """
    从输入数据构建完整的上下文字典
    info_data: dict 包含所有输入信息
    full_case: 是否按 token 展开完整大小写组合（对应「大小写组合」规则开关）

    出口统一做两道处理：输入归一化（全角转半角）+ 变体只保留 ASCII。
    自定义规则里任何占位符都不可能再吐出汉字。
    """
    from core.name_handler import get_name_context, _pinyin_syllables
    from core.case_handler import case_variants
    from core.birthday_handler import get_birthday_context
    from core.phone_handler import get_phone_context
    from core.idcard_handler import get_idcard_context
    from core.email_handler import get_email_context
    from core.id_handler import get_id_context
    from core.util import ascii_variants, has_chinese, normalize_info

    info_data = normalize_info(info_data)
    context = {}

    context.update(get_name_context(
        info_data.get('chinese_name', ''),
        info_data.get('english_name', ''),
        info_data.get('nickname', ''),
        full_case,
    ))
    context.update(get_birthday_context(info_data.get('birthday', '')))
    context.update(get_phone_context(info_data.get('phone', '')))
    context.update(get_idcard_context(info_data.get('idcard', '')))
    context.update(get_email_context(info_data.get('email', '')))

    if info_data.get('work_id'):
        context.update(get_id_context(info_data['work_id'], '工号'))
    if info_data.get('student_id'):
        context.update(get_id_context(info_data['student_id'], '学号'))

    if info_data.get('qq'):
        context['QQ'] = [info_data['qq']]
    if info_data.get('wechat'):
        wechat = info_data['wechat']
        context['微信'] = case_variants(wechat.split() or [wechat], '', full_case)
    if info_data.get('company'):
        company = info_data['company']
        if has_chinese(company):
            context['公司'] = case_variants(_pinyin_syllables(company), '', full_case)
        else:
            context['公司'] = case_variants(company.split() or [company], '', full_case)
    if info_data.get('company_abbr'):
        abbr = info_data['company_abbr']
        context['公司缩写'] = case_variants(abbr.split() or [abbr], '', full_case)
    if info_data.get('city'):
        city = info_data['city']
        if has_chinese(city):
            context['城市'] = case_variants(_pinyin_syllables(city), '', full_case)
        else:
            context['城市'] = case_variants(city.split() or [city], '', full_case)
    if info_data.get('username'):
        uid = info_data['username']
        context['常用ID'] = case_variants(uid.split() or [uid], '', full_case)
    if info_data.get('pet_name'):
        pet = info_data['pet_name']
        if has_chinese(pet):
            context['宠物'] = case_variants(_pinyin_syllables(pet), '', full_case)
        else:
            context['宠物'] = case_variants(pet.split() or [pet], '', full_case)

    if info_data.get('partner_name'):
        partner = info_data['partner_name']
        if has_chinese(partner):
            syllables = _pinyin_syllables(partner)
            context['伴侣姓名'] = case_variants(syllables, '', full_case)
            context['伴侣首字母'] = case_variants([p[0] for p in syllables], '', full_case)
        else:
            context['伴侣姓名'] = case_variants(partner.split() or [partner], '', full_case)

    if info_data.get('partner_birthday'):
        for k, v in get_birthday_context(info_data['partner_birthday']).items():
            context['伴侣' + k] = v

    for key, label in (('father_name', '父亲姓名'), ('mother_name', '母亲姓名')):
        name = info_data.get(key)
        if name:
            if has_chinese(name):
                context[label] = case_variants(_pinyin_syllables(name), '', full_case)
            else:
                context[label] = case_variants(name.split() or [name], '', full_case)

    # 最终闸门：所有占位符变体只保留 ASCII，空的直接剔除
    clean = {}
    for key, variants in context.items():
        kept = ascii_variants(variants)
        if kept:
            clean[key] = kept
    return clean
