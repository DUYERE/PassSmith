"""字典运算：合并去重 / 差集（排除已试密码）

纯文件逻辑，不依赖 Qt，便于单元测试与复用。
"""


def _detect_encoding(path):
    """探测字典文件编码：读前 64KB 试解码，UTF-8 不通则回退 GBK

    本工具自身能导出 GBK 字典，合并功能却按 UTF-8 硬读、配 errors='ignore'
    静默丢字符，表现为合并后含中文的条目直接消失。密码字典绝大多数是纯
    ASCII（两种编码互兼容），探测只为兜住含中文/特殊字符的文件。
    """
    try:
        with open(path, 'rb') as f:
            head = f.read(65536)
    except OSError:
        return 'utf-8'
    # 截断处可能落在多字节字符中间，去掉尾部几字节再判定
    probe = head[:-4] if len(head) > 8 else head
    for encoding in ('utf-8-sig', 'gbk'):
        try:
            probe.decode(encoding)
            return encoding
        except UnicodeDecodeError:
            continue
    return 'utf-8'


def read_passwords(path):
    """逐行读取字典文件：跳过空行与 `#` 注释行（自动识别 UTF-8 / GBK）"""
    encoding = _detect_encoding(path)
    with open(path, 'r', encoding=encoding, errors='ignore') as f:
        for line in f:
            pwd = line.rstrip('\r\n')
            if pwd and not pwd.startswith('#'):
                yield pwd


def merge_passwords(files):
    """多文件求并集，保序去重（先出现的先保留）"""
    seen = {}
    for path in files:
        for pwd in read_passwords(path):
            seen.setdefault(pwd, True)
    return list(seen)


def diff_passwords(base_file, exclude_files):
    """差集：基准字典按原顺序保留、剔除出现在排除字典中的密码

    返回 (结果列表, 基准条数, 排除集大小)。
    用途：二次爆破时把已试过/已锁定的密码从新字典里去掉，省账号锁定次数。
    """
    base = dict.fromkeys(read_passwords(base_file))
    excluded = set()
    for path in exclude_files:
        excluded.update(read_passwords(path))
    result = [pwd for pwd in base if pwd not in excluded]
    return result, len(base), len(excluded)
