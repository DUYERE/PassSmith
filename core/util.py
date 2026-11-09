"""通用小工具（无项目内依赖，所有模块都可就近引用）"""

import os
import re
import sys
import unicodedata


def app_base_dir():
    """程序基准目录：打包后为 exe 所在目录，开发环境为项目根

    PyInstaller 打包后 __file__ 指向解压出的临时目录，不能用来定位可写数据。
    """
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def resource_dirs(subdir):
    """只读资源的候选目录（按优先级）

    打包后优先 exe 同级的 config/、assets/（用户可直接改），
    找不到再回退 PyInstaller 内置副本（sys._MEIPASS）。
    """
    dirs = [os.path.join(app_base_dir(), subdir)]
    meipass = getattr(sys, '_MEIPASS', None)
    if meipass and getattr(sys, 'frozen', False):
        dirs.append(os.path.join(meipass, subdir))
    return dirs


def resolve_resource_dir(subdir):
    """返回第一个实际存在的资源目录，都不存在时回退首个候选"""
    candidates = resource_dirs(subdir)
    for path in candidates:
        if os.path.isdir(path):
            return path
    return candidates[0]


CONFIG_DIR = resolve_resource_dir('config')

# 密码字典只允许可打印 ASCII（0x20~0x7E）。
# 汉字、全角字符、emoji、制表符/换行一旦混进来，轻则整条密码作废，重则破坏字典逐行格式。
_ASCII_PRINTABLE_RE = re.compile(r'[\x20-\x7e]+')
_CHINESE_RE = re.compile(r'[\u4e00-\u9fff]')
# 列表分隔符：英文逗号 / 中文逗号 / 顿号 / 分号 / 换行
_LIST_SEPARATOR_RE = re.compile(r'[,，、;；\r\n]+')
# 允许空格作分隔符的版本（仅用于分隔符这类单字符符号列表，密码列表不能用）
_LIST_SEPARATOR_SPACE_RE = re.compile(r'[,，、;；\s]+')
# 零宽字符 / 行分隔符：肉眼不可见，会以隐形字符形式混进密码，必须先剔除
_INVISIBLE_RE = re.compile(r'[\u200b-\u200f\u2028-\u202f\ufeff]')


def split_list_text(text, allow_space=False):
    """按中英文逗号/顿号/分号/换行切分列表文本

    中文输入法下极易打出全角逗号（，）、顿号（、），只认英文逗号会让整行
    被当成一条超长弱口令，随后被长度筛选静默丢弃——表现为「我加的词不生效」。

    allow_space=True 时空格也算分隔符，仅用于「分隔符」这类单字符符号列表；
    密码列表不能开，否则含空格的真实密码会被拆坏。
    """
    if not text:
        return []
    pattern = _LIST_SEPARATOR_SPACE_RE if allow_space else _LIST_SEPARATOR_RE
    return [part.strip() for part in pattern.split(text) if part.strip()]


def load_config_file(filename, default=None):
    """加载配置目录下的行式配置（注释仅限 `# ` 开头，即 # 后必须跟空白）

    注意：不能按「# 开头」判注释——`#` 本身就是合法后缀/分隔符，
    老规则会把它整行吞掉，导致 # 后缀从未生效。
    按 resource_dirs 的顺序逐个目录查找，文件缺失时返回 default。
    """
    for config_dir in resource_dirs('config'):
        filepath = os.path.join(config_dir, filename)
        items = []
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('# '):
                        items.append(line)
        except FileNotFoundError:
            continue
        if items:
            return items
    return list(default) if default is not None else []


def uniq(items):
    """保序去重（替代 list(set(...))，保证生成字典顺序跨运行稳定）"""
    return list(dict.fromkeys(items))


def uniq_filter(items):
    """保序去重 + 丢弃空值/None"""
    return [v for v in dict.fromkeys(items) if v]


def has_chinese(text):
    """是否包含中文字符"""
    return bool(text and _CHINESE_RE.search(text))


def is_ascii_password(pwd):
    """是否为合法密码：只含可打印 ASCII，且首尾无空白

    首尾空白必须拒绝——尾部空格肉眼不可见，会让整条密码失效；
    换行/制表符会直接破坏「一行一个密码」的字典格式。
    """
    if not pwd or pwd != pwd.strip():
        return False
    return _ASCII_PRINTABLE_RE.fullmatch(pwd) is not None


def ascii_variants(items):
    """只保留合法 ASCII 变体（保序去重），汉字/全角/emoji 变体一律丢弃"""
    return [v for v in uniq_filter(items) if is_ascii_password(v)]


def is_mixed_case(text):
    """是否同时包含大写和小写字母（等保/AD「大小写混合」策略的判定依据）"""
    if not text:
        return False
    return any(c.isupper() for c in text) and any(c.islower() for c in text)


def normalize_text(text):
    """输入归一化：NFKC（全角转半角、兼容字符归一）→ 去不可见字符 → 去首尾空白

    中文输入法下很容易打出全角数字/字母（１３８、ｚｈａｎｇ），
    不归一化会让 isdigit() 判定通过却生成全角密码。
    """
    if not text:
        return ''
    s = unicodedata.normalize('NFKC', str(text))
    s = _INVISIBLE_RE.sub('', s)
    return s.strip()


def normalize_info(info):
    """归一化全部文本输入字段，非字符串值原样保留"""
    if not info:
        return {}
    return {k: normalize_text(v) if isinstance(v, str) else v for k, v in info.items()}
