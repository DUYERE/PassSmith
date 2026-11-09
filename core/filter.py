"""筛选模块 - 字符集合规/去重/长度/复杂度/目标站点策略筛选"""

from core.util import is_ascii_password, is_mixed_case

# 目标站点字符集模式：
#   any   — 任意可打印 ASCII（默认，兼容性最好）
#   alnum — 仅字母数字（很多内网系统/老 OA 禁止特殊字符）
#   digit — 仅数字（锁屏 PIN、支付密码等纯数字场景）
CHARSET_MODES = ('any', 'alnum', 'digit')


def filter_by_charset(passwords, charset_mode='any'):
    """第一道闸门：可打印 ASCII + 目标站点字符集约束

    汉字、全角字符、emoji、制表符/换行在真实登录系统中不可能成立，
    换行还会破坏「一行一个密码」的字典格式；charset_mode 再把不符合
    目标站点字符集策略的条目提前挡掉，避免导出后被系统直接拒绝。
    """
    if charset_mode == 'alnum':
        for pwd in passwords:
            if is_ascii_password(pwd) and pwd.isalnum():
                yield pwd
    elif charset_mode == 'digit':
        for pwd in passwords:
            if is_ascii_password(pwd) and pwd.isdigit():
                yield pwd
    else:
        for pwd in passwords:
            if is_ascii_password(pwd):
                yield pwd


def filter_by_length(passwords, min_len=4, max_len=20):
    """按长度筛选密码"""
    for pwd in passwords:
        if min_len <= len(pwd) <= max_len:
            yield pwd


def filter_by_complexity(passwords, require_digit=False, require_alpha=False,
                         require_special=False, require_mixed_case=False):
    """按复杂度筛选密码

    require_digit:      必须包含数字
    require_alpha:      必须包含字母
    require_special:    必须包含特殊字符
    require_mixed_case: 必须同时包含大写和小写字母（等保/AD 常见策略）
    """
    for pwd in passwords:
        has_digit = any(ch.isdigit() for ch in pwd)
        has_alpha = any(ch.isalpha() for ch in pwd)
        has_special = any(not ch.isalnum() for ch in pwd)

        if require_digit and not has_digit:
            continue
        if require_alpha and not has_alpha:
            continue
        if require_special and not has_special:
            continue
        if require_mixed_case and not is_mixed_case(pwd):
            continue

        yield pwd


def deduplicate(passwords):
    """增量去重"""
    seen = set()
    for pwd in passwords:
        if pwd not in seen:
            seen.add(pwd)
            yield pwd


def filter_passwords(passwords, min_len=5, max_len=20,
                     require_digit=False, require_alpha=False, require_special=False,
                     require_mixed_case=False, charset_mode='any', dedup=True):
    """综合筛选管道（字符集合规为固定第一道，任何生成路径都绕不过去）"""
    result = filter_by_charset(passwords, charset_mode)

    if dedup:
        result = deduplicate(result)

    if min_len > 0 or max_len < 999:
        result = filter_by_length(result, min_len, max_len)

    if require_digit or require_alpha or require_special or require_mixed_case:
        result = filter_by_complexity(
            result, require_digit, require_alpha, require_special, require_mixed_case)

    return result
