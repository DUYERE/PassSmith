"""生日处理模块 - 生成多种日期格式变体"""

import re

from core.util import uniq_filter

_CN_YEAR_MONTH_RE = re.compile(r'[年月]')


def _normalize_date_text(text):
    """把各种日期写法统一成 `YYYY-MM-DD` 或 `YY-MM-DD`

    支持：1988-03-12、1988/03/12、1988.03.12、1988年3月12日、19880312、88-03-12（两位年自动补世纪）。

    无法识别时返回空串——绝不能返回原串，否则 `1988年3月12日` 会作为密码素材
    产出 `zhangsan1988年3月12日` 这类永远不可能命中的垃圾。
    """
    s = _CN_YEAR_MONTH_RE.sub('-', text.strip())
    s = s.replace('日', '').replace('/', '-').replace('.', '-').replace(' ', '-')
    s = re.sub(r'-+', '-', s).strip('-')

    parts = [p for p in s.split('-') if p]
    if len(parts) == 3 and len(parts[0]) == 2 and parts[0].isdigit():
        yy = int(parts[0])
        parts[0] = str(2000 + yy if yy <= 30 else 1900 + yy)
        return '-'.join(parts)
    return s


def _valid_date(year, month, day):
    """校验年月日是否构成真实日期

    不校验会让 1990-13-45 产出 19901345、199015 这类永远不可能命中的垃圾组合。
    """
    try:
        y, m, d = int(year), int(month), int(day)
    except (TypeError, ValueError):
        return False
    if not (1900 <= y <= 2100) or not (1 <= m <= 12) or not (1 <= d <= 31):
        return False
    # 逐月校验天数（含闰年）
    days_in_month = [31, 29 if (y % 4 == 0 and y % 100 != 0) or y % 400 == 0 else 28,
                     31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    return d <= days_in_month[m - 1]


def get_birthday_variants(birthday_str):
    """从生日字符串生成各种格式变体
    输入格式：1990-01-15 或 19900115（也容忍 / . 年月日 等写法）
    """
    if not birthday_str or not birthday_str.strip():
        return []

    normalized = _normalize_date_text(birthday_str)
    if not normalized:
        return []

    digits = normalized.replace('-', '')

    if '-' not in normalized:
        if len(digits) == 8:
            parts = [digits[:4], digits[4:6], digits[6:8]]
            if not _valid_date(*parts):
                return []
        elif len(digits) == 6:
            parts = [digits[:2], digits[2:4], digits[4:6]]
            # YYMMDD：只校验月日（世纪由前缀补全）
            if not (parts[1].isdigit() and parts[2].isdigit()
                    and 1 <= int(parts[1]) <= 12 and 1 <= int(parts[2]) <= 31):
                return []
            # 6位格式无法确定世纪，添加20和19前缀
            variants = _generate_from_parts(parts[0], parts[1], parts[2])
            extra = []
            for v in list(variants):
                if not v.startswith('19') and not v.startswith('20'):
                    extra.append('19' + v if len(v) <= 6 else v)
                    extra.append('20' + v if len(v) <= 6 else v)
            variants.extend(extra)
            return uniq_filter(variants)
        else:
            return []
    else:
        parts = [p for p in normalized.split('-') if p]
        if len(parts) != 3:
            return []

    year, month, day = parts
    if not _valid_date(year, month, day):
        return []
    return _generate_from_parts(year, month, day)


def _generate_from_parts(year, month, day):
    """从年月日部件生成变体"""
    # 确保月和日有前导零
    month_pad = month.zfill(2)
    day_pad = day.zfill(2)

    # 年可能是2位或4位
    year_short = year[-2:] if len(year) == 4 else year

    variants = [
        year + month_pad + day_pad,       # 19900115
        year,                              # 1990
        year_short,                        # 90
        month_pad + day_pad,               # 0115
        day_pad + month_pad,               # 1501
        year_short + month_pad + day_pad,  # 900115
        day_pad + month_pad + year_short,  # 150190
        month_pad + day_pad + year_short,  # 011590
        year + month_pad,                  # 199001
        # 注意：不放「年+日」（199015）——1990 年 15 月是不存在的日期，没人用它做密码
    ]

    # 去除前导零的变体
    for v in list(variants):
        if v.startswith('0'):
            stripped = v.lstrip('0') or '0'
            if stripped != v:
                variants.append(stripped)

    return uniq_filter(variants)


def get_birthday_context(birthday_str):
    """生成生日相关的上下文字典，用于自定义规则解析"""
    if not birthday_str or not birthday_str.strip():
        return {}

    birthday_str = birthday_str.strip()

    # 解析年月日
    if '-' in birthday_str:
        parts = birthday_str.split('-')
    elif '/' in birthday_str:
        parts = birthday_str.split('/')
    else:
        s = birthday_str.replace(' ', '')
        if len(s) == 8:
            parts = [s[:4], s[4:6], s[6:8]]
        else:
            return {}

    if len(parts) != 3:
        return {}

    year, month, day = parts
    month_pad = month.zfill(2)
    day_pad = day.zfill(2)
    year_short = year[-2:]

    context = {
        '生日全': [year + month_pad + day_pad],
        '生日年': [year, year_short],
        '生日月日': [month_pad + day_pad, day_pad + month_pad],
        '生日短': [year_short + month_pad + day_pad],
        '生日月': [month_pad, month],
        '生日日': [day_pad, day],
    }

    return context
