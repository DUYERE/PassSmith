"""手机号处理模块 - 生成完整/后8/后6/后4/号段/号段+后4等变体"""

from core.util import uniq_filter


def normalize_phone(phone):
    """归一化手机号：剥离空格/短横，容忍 +86 国家码与括号写法

    返回纯数字串；凑不出 4~11 位数字时返回空串。
    绝不回退原始输入——`+8613812345678`、`(138)1234-5678` 这类串一旦进入
    组合阶段，会拼出 `zhangsan+8613812345678` 这种任何系统都不可能存在的密码，
    只是给字典灌垃圾。手机号字段的输入必然全是数字，凑不出数字就是误填。
    """
    if not phone or not phone.strip():
        return ''
    cleaned = phone.strip().replace(' ', '').replace('-', '')
    digits = cleaned if cleaned.isdigit() else ''.join(ch for ch in cleaned if ch.isdigit())
    if not digits:
        return ''

    # 13 位且以 86 开头：带国家码。`+86...` 与 Excel 复制后丢了加号的 `86...` 都要认
    if len(digits) == 13 and digits.startswith('86'):
        digits = digits[2:]
    return digits if 4 <= len(digits) <= 11 else ''


def get_phone_variants(phone):
    """从手机号生成变体"""
    phone = normalize_phone(phone)
    if not phone:
        return []

    variants = []

    if len(phone) == 11:
        variants.extend([
            phone,                    # 完整11位
            phone[3:],                # 后8位
            phone[5:],                # 后6位
            phone[7:],                # 后4位
            # 注意：不放前 3 位号段单独变体——「zhangsan138」这类组合没人用，
            # 号段只在「号段+后4」的组合形态里有意义
            phone[:3] + phone[7:],    # 号段+后4位
        ])
    elif len(phone) >= 8:
        variants.extend([
            phone,                    # 完整
            phone[3:],                # 后N位
            phone[-4:],               # 后4位
            phone[-6:],               # 后6位
            phone[-8:],               # 后8位
        ])
    elif len(phone) >= 6:
        variants.extend([
            phone,
            phone[-4:],
            phone[-6:],
        ])
    else:
        variants.append(phone)

    return uniq_filter(variants)


def get_phone_context(phone):
    """生成手机号相关的上下文字典"""
    phone = normalize_phone(phone)
    if not phone:
        return {}

    context = {}

    if len(phone) == 11:
        context['手机号'] = [phone]
        context['手机后8'] = [phone[3:]]
        context['手机后6'] = [phone[5:]]
        context['手机后4'] = [phone[7:]]
        context['手机号段'] = [phone[:3]]
        context['手机号段后4'] = [phone[:3] + phone[7:]]
    elif len(phone) >= 4:
        context['手机号'] = [phone]
        context['手机后4'] = [phone[-4:]]
        if len(phone) >= 6:
            context['手机后6'] = [phone[-6:]]
        if len(phone) >= 8:
            context['手机后8'] = [phone[-8:]]

    return context
