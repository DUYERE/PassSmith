"""文件导出工具 - TXT/CSV/分片导出"""

import os
import time
import csv


def export_txt(passwords, filepath, encoding='utf-8', split_size=None):
    """
    导出密码字典为TXT文件
    passwords: 密码列表或生成器
    filepath: 输出文件路径
    encoding: 文件编码
    split_size: 分片大小（None为不分片）
    返回: 导出的文件路径列表
    """
    # 转为列表以便多次遍历
    if not isinstance(passwords, list):
        passwords = list(passwords)

    if not passwords:
        return []

    if split_size and len(passwords) > split_size:
        return _split_export(passwords, filepath, encoding, split_size)
    else:
        _write_single_txt(passwords, filepath, encoding)
        return [filepath]


def _write_single_txt(passwords, filepath, encoding):
    """写入单个TXT文件"""
    with open(filepath, 'w', encoding=encoding) as f:
        f.write("# 社工密码字典 - 仅供授权安全测试使用\n")
        f.write(f"# 生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"# 总计: {len(passwords)} 条\n\n")
        for pwd in passwords:
            f.write(pwd + '\n')


def _split_export(passwords, filepath, encoding, split_size):
    """分片导出"""
    base, ext = os.path.splitext(filepath)
    total = len(passwords)
    file_count = (total + split_size - 1) // split_size
    output_files = []

    for i in range(file_count):
        part_filepath = f"{base}_part{i+1}{ext}"
        start = i * split_size
        end = min(start + split_size, total)

        with open(part_filepath, 'w', encoding=encoding) as f:
            f.write(f"# 社工密码字典 (分片 {i+1}/{file_count}) - 仅供授权安全测试使用\n")
            f.write(f"# 生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"# 本片: {end - start} 条 / 总计: {total} 条\n\n")
            for pwd in passwords[start:end]:
                f.write(pwd + '\n')

        output_files.append(part_filepath)

    return output_files


# Excel 会把以这些字符开头的内容当成公式（CSV 注入），显示 #NAME? 甚至执行
_EXCEL_FORMULA_PREFIX = ('=', '+', '-', '@', '\t', '\r')


def _excel_text_guard(value):
    """给会被 Excel 误解析的值加单引号前缀，强制按文本处理

    三类必须处理：
    1. `= + - @` 开头 —— 当公式解析，显示 #NAME?（CSV 注入风险）
    2. `0` 开头的纯数字 —— 前导零被吃掉（000000 → 0）
    3. ≥15 位纯数字 —— 超出 Excel 15 位精度，被转成科学计数法（身份证/长号码）

    单引号是 Excel 的「强制文本」标记：单元格显示时不可见，复制出来也不含，
    所以不影响人工取值。但用文本编辑器/脚本读会多一个引号——
    机器处理请用 TXT 导出，CSV 只面向 Excel 查看。
    """
    if not value:
        return value
    if value[0] in _EXCEL_FORMULA_PREFIX:
        return "'" + value
    if value[0] == '0' and value.isdigit():
        return "'" + value
    if value.isdigit() and len(value) >= 15:
        return "'" + value
    return value


def export_csv(passwords, filepath, encoding='utf-8'):
    """导出密码字典为CSV文件（单列「密码」）

    原实现第二列是「序号」——数行号即可得到，毫无价值。
    来源规则需要生成时全程追踪，当前架构不支持，不再承诺。

    编码说明：Excel 在简体中文环境按 GBK 解析无 BOM 的 CSV，中文表头必乱码，
    因此 UTF-8 输出统一加 BOM（utf-8-sig）。TXT 恰好相反——绝不能带 BOM，
    否则 BOM 会被爆破工具当成第一条密码的一部分。
    """
    if not isinstance(passwords, list):
        passwords = list(passwords)

    if encoding.lower().replace('-', '') in ('utf8', 'utf'):
        encoding = 'utf-8-sig'

    with open(filepath, 'w', encoding=encoding, newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["密码"])
        for pwd in passwords:
            writer.writerow([_excel_text_guard(pwd)])

    return filepath


def export_tiers(passwords, filepath, tiers=(100, 1000), encoding='utf-8'):
    """按优先级分档导出：Top-N 小字典 + 全量

    在线爆破受账号锁定策略限制，实际打法是先试 Top100、再 Top1000、最后全量。
    这里一次产出三档文件，省去手工切分。
    返回 [(label, path, count), ...]
    """
    if not isinstance(passwords, list):
        passwords = list(passwords)
    if not passwords:
        return []

    base, ext = os.path.splitext(filepath)
    results = []
    for n in sorted(tiers):
        if len(passwords) <= n:
            continue
        path = f"{base}_top{n}{ext}"
        _write_single_txt(passwords[:n], path, encoding)
        results.append((f"Top {n}", path, n))

    _write_single_txt(passwords, filepath, encoding)
    results.append(("全量", filepath, len(passwords)))
    return results


def estimate_file_size(passwords, sample_count=1000):
    """预估文件大小"""
    if not passwords:
        return 0

    sample = passwords[:sample_count]
    if not sample:
        return 0

    avg_len = sum(len(p) for p in sample) / len(sample)
    return int(len(passwords) * (avg_len + 1))  # +1 for newline


def format_size(bytes_size):
    """格式化文件大小（边界取 >=：1024B 显示 1.0KB 而不是 1024B）"""
    if bytes_size >= 1024 * 1024:
        return f"{bytes_size / 1024 / 1024:.1f}MB"
    elif bytes_size >= 1024:
        return f"{bytes_size / 1024:.1f}KB"
    else:
        return f"{bytes_size}B"
