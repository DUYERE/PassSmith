"""模板保存/加载工具"""

import os
import re
import json

from core.util import app_base_dir


TEMPLATE_DIR = os.path.join(app_base_dir(), 'output', 'templates')

# 文件名非法字符（Windows 最严格）：路径分隔符会直接造成越界写入
_INVALID_CHARS = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


def safe_template_name(name):
    """模板名安全化：剔除路径分隔符与非法字符，拒绝纯点号/空名

    模板名直接拼进文件路径，不处理会让 `../evil` 写到 templates 目录之外。
    """
    cleaned = _INVALID_CHARS.sub('_', (name or '').strip())
    cleaned = cleaned.strip('. ')
    return cleaned or 'template'


def save_template(name, info_data, rules_config):
    """保存配置模板"""
    os.makedirs(TEMPLATE_DIR, exist_ok=True)

    name = safe_template_name(name)
    template = {
        'name': name,
        'info_data': info_data,
        'rules_config': rules_config,
    }

    filepath = os.path.join(TEMPLATE_DIR, f"{name}.json")
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(template, f, ensure_ascii=False, indent=2)

    return filepath


def load_template(name):
    """加载配置模板"""
    filepath = os.path.join(TEMPLATE_DIR, f"{safe_template_name(name)}.json")

    if not os.path.exists(filepath):
        return None

    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def list_templates():
    """列出所有模板"""
    if not os.path.exists(TEMPLATE_DIR):
        return []

    templates = []
    for fname in os.listdir(TEMPLATE_DIR):
        if fname.endswith('.json'):
            name = fname[:-5]
            try:
                with open(os.path.join(TEMPLATE_DIR, fname), 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    templates.append({
                        'name': name,
                        'info_keys': list(data.get('info_data', {}).keys()),
                    })
            except Exception:
                templates.append({'name': name, 'info_keys': []})

    return templates


def delete_template(name):
    """删除模板"""
    filepath = os.path.join(TEMPLATE_DIR, f"{safe_template_name(name)}.json")
    if os.path.exists(filepath):
        os.remove(filepath)
        return True
    return False
