"""大小写变体生成 - 按 token（音节/首字母）边界组合，不做逐字符 2^n 枚举

`zhangsan` 逐字符有大写组合 2^8 = 256 种，其中 250 种没人用，只会把字典撑爆。
真实密码习惯只有 3~4 种：zhangsan / Zhangsan / ZHANGSAN / ZhangSan。

首字母缩写是例外——`zs` 的 zs / Zs / ZS / zS 四种写法都真实存在，值得全枚举。
"""

from core.util import uniq_filter


def token_case_forms(tokens):
    """返回 token 序列的标准大小写形态，每个形态是一个 token 列表（保序）"""
    lower = [t.lower() for t in tokens if t]
    if not lower:
        return []

    # 纯首字母缩写（zs / zsm）
    if all(len(t) == 1 for t in lower):
        if len(lower) == 2:
            a, b = lower
            return [
                [a, b],                  # zs
                [a.upper(), b],          # Zs
                [a.upper(), b.upper()],  # ZS
                [a, b.upper()],          # zS
            ]
        return [
            lower,                                        # zsm
            [lower[0].upper()] + lower[1:],               # Zsm
            [t.upper() for t in lower],                   # ZSM
        ]

    forms = [
        lower,                                            # zhangsan
        [lower[0][:1].upper() + lower[0][1:]] + lower[1:],  # Zhangsan
        [t.upper() for t in lower],                       # ZHANGSAN
    ]
    # CamelCase 只在每个 token 都 ≥2 字符时成立：zhang+c → ZhangC 是垃圾
    if all(len(t) >= 2 for t in lower):
        forms.append([t[:1].upper() + t[1:] for t in lower])  # ZhangSan
    return forms


def case_variants(tokens, sep='', full=True):
    """token 序列 × 大小写形态 × 分隔符

    full=False 时只取第一种形态（全小写），用于关闭「大小写组合」规则时压缩字典。
    """
    forms = token_case_forms(tokens)
    if not full:
        forms = forms[:1]
    return uniq_filter(sep.join(f) for f in forms)


def join_case_variants(tokens, seps=('',), full=True):
    """多种分隔符分别展开，同一分隔符的形态连续排列"""
    out = []
    for sep in seps:
        out.extend(case_variants(tokens, sep, full))
    return uniq_filter(out)
