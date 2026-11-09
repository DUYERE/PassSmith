# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置（onedir 模式）

构建：D:/DevTools/Python3.10/python -m PyInstaller passsmith.spec --noconfirm

产物结构（dist/PassSmith/）：
    PassSmith.exe
    config/        ← 从项目 config 复制，用户可直接改弱口令/后缀等
    assets/        ← 图标资源
    output/        ← 运行时生成（字典/templates/历史）
    _internal/     ← PyInstaller 依赖与内置资源副本

运行时 core.util.app_base_dir() 在 frozen 环境下返回 exe 所在目录，
因此 config/assets 优先读 exe 同级（可改），找不到才回退 _internal 内置副本。
"""

import os

block_cipher = None

PROJECT_ROOT = os.path.abspath('.')

a = Analysis(
    ['main.py'],
    pathex=[PROJECT_ROOT],
    binaries=[],
    # 只读资源打两份：一份进 _internal 兜底，构建脚本会再复制一份到 dist 同级供用户修改
    datas=[
        ('config', 'config'),
        ('assets', 'assets'),
    ],
    hiddenimports=['pypinyin'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['pytest', 'tests', 'tkinter'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='PassSmith',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,          # GUI 程序，不弹控制台
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(PROJECT_ROOT, 'assets', 'favicon.ico'),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='PassSmith',
)
