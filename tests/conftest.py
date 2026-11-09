"""pytest 配置：把项目根加入 sys.path，提供公共 fixture

运行：D:/DevTools/Python3.10/python -m pytest tests/ -q
（默认 python 3.13 沙箱没装 pytest）
"""

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.combiner import PasswordGenerator  # noqa: E402


@pytest.fixture(scope='session')
def generator():
    return PasswordGenerator()


@pytest.fixture
def base_rules():
    """默认规则配置（不依赖 UI）"""
    return {
        'max_depth': 3,
        'min_len': 5,
        'max_len': 20,
        'quick_rules': {},
        'custom_rules': '',
        'separators': ['.', '_', '-', '@', '#'],
    }


@pytest.fixture
def basic_info():
    return {'chinese_name': '张三', 'birthday': '1990-01-15', 'phone': '13812345678'}
