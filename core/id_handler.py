"""工号/学号处理模块 - 生成编号变体"""

from core.util import uniq_filter


def get_id_variants(id_str):
    """从工号/学号生成变体"""
    if not id_str or not id_str.strip():
        return []

    id_str = id_str.strip()

    variants = [id_str]

    # 去除前导零
    stripped = id_str.lstrip('0') or '0'
    if stripped != id_str:
        variants.append(stripped)

    # 后4位
    if len(id_str) >= 4:
        variants.append(id_str[-4:])

    # 后6位
    if len(id_str) >= 6:
        variants.append(id_str[-6:])

    # 如果有字母前缀，提取数字部分和字母部分
    alpha_part = ''
    num_part = ''
    for ch in id_str:
        if ch.isalpha():
            alpha_part += ch
        else:
            num_part += ch

    if alpha_part and num_part:
        variants.append(num_part)
        variants.append(alpha_part.lower())
        variants.append(alpha_part.upper())
        variants.append(alpha_part.lower() + num_part)
        variants.append(alpha_part.upper() + num_part)

    return uniq_filter(variants)


def get_id_context(id_str, label='工号'):
    """生成工号/学号相关的上下文字典"""
    if not id_str or not id_str.strip():
        return {}

    id_str = id_str.strip()

    context = {
        label: [id_str],
    }

    stripped = id_str.lstrip('0') or '0'
    if stripped != id_str:
        context[label].append(stripped)

    return context
