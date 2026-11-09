"""邮箱处理模块 - 生成前缀及变体"""

from core.util import normalize_text, uniq_filter

# 常见顶级域：用来区分「邮箱前缀 zhang.san」和「域名 nana.qq.com」
_COMMON_TLDS = frozenset({
    'com', 'cn', 'net', 'org', 'edu', 'gov', 'io', 'co', 'me',
    'info', 'biz', 'xyz', 'top', 'cc', 'tv', 'hk', 'tw', 'jp', 'uk',
})


def _resolve_prefix(raw):
    """处理「没有 @ 的输入」：域名取首段，邮箱前缀写法整串保留

    `nana.qq.com` 是贴了域名，取首段 `nana`；
    但 `zhang.san` 是企业邮箱前缀的常见写法，一律按点切会把 `.san` 丢掉，
    用户填的前缀直接失效。用末段是否为常见 TLD 来区分这两种情况。
    """
    raw = raw.strip()
    if not raw:
        return ''
    parts = [p for p in raw.split('.') if p]
    if len(parts) >= 2 and parts[-1].lower() in _COMMON_TLDS:
        return parts[0]
    return raw


def get_email_variants(email):
    """从邮箱生成变体"""
    if not email or not email.strip():
        return []

    email = normalize_text(email).strip()

    if '@' not in email:
        # 没有 @：用户可能只填了前缀（zhang.san），也可能贴了完整域名（nana.qq.com）
        prefix = _resolve_prefix(email)
        if not prefix:
            return []
        return uniq_filter([prefix, prefix.lower(), prefix.capitalize(), prefix.upper()])

    prefix, domain = email.split('@', 1)
    prefix = prefix.strip()
    if not prefix:
        return []

    variants = [
        prefix,                         # 邮箱前缀
        prefix.capitalize(),            # 首字母大写
        prefix.upper(),                 # 全大写
        prefix.lower(),                 # 全小写
        email,                          # 完整邮箱
    ]

    # 点分隔变体
    if '.' in prefix:
        variants.extend([
            prefix.replace('.', ''),        # 去点
            prefix.replace('.', '_'),        # 点换下划线
            prefix.replace('.', '-'),        # 点换短横线
            prefix.replace('.', '').capitalize(),  # 去点首字母大写
        ])

    # 数字后缀变体（如 zhang123 -> zhang）
    stripped = prefix.rstrip('0123456789')
    if stripped and stripped != prefix:
        variants.append(stripped)
        num_part = prefix[len(stripped):]
        if num_part:
            variants.append(num_part)

    return uniq_filter(variants)


def get_email_context(email):
    """生成邮箱相关的上下文字典"""
    if not email or not email.strip():
        return {}

    email = email.strip()

    if '@' not in email:
        prefix = _resolve_prefix(email)
        return {'邮箱前缀': [prefix, prefix.lower(), prefix.capitalize()]} if prefix else {}

    prefix, domain = email.split('@', 1)

    context = {
        '邮箱前缀': [prefix, prefix.lower(), prefix.capitalize(), prefix.upper()],
    }

    if '.' in prefix:
        context['邮箱前缀'].extend([
            prefix.replace('.', ''),
            prefix.replace('.', '_'),
            prefix.replace('.', '-'),
        ])
        context['邮箱前缀'] = uniq_filter(context['邮箱前缀'])

    return context
