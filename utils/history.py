"""历史记录管理"""

import os
import json
import time

from core.util import app_base_dir


HISTORY_FILE = os.path.join(app_base_dir(), 'output', '.history.json')
MAX_HISTORY = 10


def save_history(info_summary, rules_summary, count):
    """保存生成历史"""
    history = load_history()

    entry = {
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'info_summary': info_summary,
        'rules_summary': rules_summary,
        'count': count,
    }

    history.insert(0, entry)
    history = history[:MAX_HISTORY]

    _write_history(history)


def load_history():
    """加载历史记录"""
    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception:
        pass
    return []


def clear_history():
    """清空历史记录"""
    _write_history([])


def _write_history(history):
    """写入历史文件"""
    try:
        os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
