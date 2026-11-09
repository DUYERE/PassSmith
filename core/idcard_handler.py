"""身份证号处理模块 - 生成后4/后6/后8/出生日期等变体"""

from core.util import uniq_filter


def get_idcard_variants(idcard):
    """从身份证号生成变体"""
    if not idcard or not idcard.strip():
        return []

    idcard = idcard.strip().replace(' ', '').upper()

    # 非纯数字（末位可能是校验位 X）时退化为「整串当素材」——护照号、军官证
    # 这类非标证件同样能当密码来源。但纯字母且过短的串必然是误填，
    # 放进去只会产出 `abc` 这种垃圾条目。
    if not idcard[:-1].isdigit():
        if len(idcard) < 4 or not any(ch.isdigit() for ch in idcard):
            return []
        return [idcard]

    variants = []

    if len(idcard) == 18:
        variants.extend([
            idcard,             # 完整18位
            idcard[-4:],        # 后4位
            idcard[-6:],        # 后6位
            idcard[-8:],        # 后8位
            idcard[6:14],       # 出生日期部分（YYYYMMDD）
            idcard[6:10],       # 出生年
            idcard[10:14],      # 出生月日
            idcard[6:12],       # 出生年月
            idcard[8:14],       # 出生月日（短年）
        ])
    elif len(idcard) == 15:
        variants.extend([
            idcard,             # 完整15位
            idcard[-4:],        # 后4位
            idcard[-6:],        # 后6位
            idcard[6:12],       # 出生日期（YYMMDD）
            idcard[6:8],        # 出生年（短）
            idcard[8:12],       # 出生月日
        ])
    else:
        # 非标准长度
        if len(idcard) >= 4:
            variants.extend([
                idcard,
                idcard[-4:],
            ])
            if len(idcard) >= 6:
                variants.append(idcard[-6:])
            if len(idcard) >= 8:
                variants.append(idcard[-8:])

    return _x_case_pairs(variants)


def _x_case_pairs(variants):
    """尾号校验位 X 的大小写对偶：...123x 与 ...123X 都有人用作密码

    variants 为列表时返回对偶列表；为 {占位符: 列表} 字典时对每个值列表分别处理。
    """
    if isinstance(variants, dict):
        return {k: _x_case_pairs(v) for k, v in variants.items()}
    out = []
    for v in variants:
        out.append(v)
        if v.endswith('x'):
            out.append(v[:-1] + 'X')
        elif v.endswith('X'):
            out.append(v[:-1] + 'x')
    return uniq_filter(out)


def get_idcard_context(idcard):
    """生成身份证相关的上下文字典"""
    if not idcard or not idcard.strip():
        return {}

    idcard = idcard.strip().replace(' ', '').upper()

    context = {}

    if len(idcard) == 18:
        context['身份证后4'] = [idcard[-4:]]
        context['身份证后6'] = [idcard[-6:]]
        context['身份证后8'] = [idcard[-8:]]
        context['身份证出生日期'] = [idcard[6:14]]
        context['身份证出生年'] = [idcard[6:10]]
        context['身份证出生月日'] = [idcard[10:14]]
    elif len(idcard) == 15:
        context['身份证后4'] = [idcard[-4:]]
        context['身份证后6'] = [idcard[-6:]]
        context['身份证出生日期'] = [idcard[6:12]]
    elif len(idcard) >= 4:
        context['身份证后4'] = [idcard[-4:]]
        if len(idcard) >= 6:
            context['身份证后6'] = [idcard[-6:]]

    return _x_case_pairs(context) if context else context
