"""社工密码字典生成器 - 程序入口"""

import sys
import os

# 确保项目根目录在 sys.path 中
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt, QSettings
from PyQt5.QtGui import QIcon, QFont

from ui.main_window import MainWindow, ORG_NAME, APP_NAME
from ui.theme import APP_ICON, DEFAULT_ZOOM, DEFAULT_THEME, THEMES, build_qss


def _enable_windows_taskbar_icon():
    """注册 AppUserModelID：必须在任何窗口创建之前调用，
    Windows 任务栏才会用应用图标替代宿主 python.exe 图标"""
    if sys.platform != 'win32':
        return
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('PassSmith.DictGen.1')
    except Exception:
        pass


def _selftest():
    """打包自检：frozen 环境下资源路径是否正确

    用法：PassSmith.exe --selftest（退出码 0 = 资源齐全）
    检查 config 行式配置与 assets 图标能否读到——这两处是打包最常见的踩坑点。
    """
    from core.util import CONFIG_DIR, load_config_file
    from ui.theme import APP_ICON, ASSET_DIR
    from utils.exporter import export_txt

    checks = []
    checks.append(('CONFIG_DIR 存在', os.path.isdir(CONFIG_DIR), CONFIG_DIR))
    checks.append(('assets 目录存在', os.path.isdir(ASSET_DIR), ASSET_DIR))
    checks.append(('应用图标存在', os.path.exists(APP_ICON), APP_ICON))

    weak = load_config_file('weak_passwords.txt')
    checks.append(('弱口令列表可读', len(weak) > 0, f'{len(weak)} 条'))

    suffixes = load_config_file('suffixes.txt')
    checks.append(('后缀列表可读', len(suffixes) > 0, f'{len(suffixes)} 条'))

    print(f"frozen={getattr(sys, 'frozen', False)}  base={os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))}")
    ok = True
    for name, passed, detail in checks:
        print(f"  [{'OK' if passed else 'FAIL'}] {name}: {detail}")
        ok = ok and passed
    print('SELFTEST', 'PASSED' if ok else 'FAILED')
    return 0 if ok else 1


def main():
    if '--selftest' in sys.argv:
        return _selftest()

    # 高DPI支持（必须在 QApplication 创建前设置）
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    QApplication.setAttribute(Qt.AA_DisableWindowContextHelpButton, True)

    # 任务栏图标归组：先于 QApplication 与任何窗口
    _enable_windows_taskbar_icon()

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setApplicationName("PassSmith")
    app.setOrganizationName("PassSmith")

    # 应用图标（窗口标题栏 + 任务栏 + Alt+Tab）
    if os.path.exists(APP_ICON):
        app.setWindowIcon(QIcon(APP_ICON))

    # 全局样式（按上次保存的主题）+ 字体
    settings = QSettings(ORG_NAME, APP_NAME)
    theme = settings.value("ui/theme", DEFAULT_THEME)
    # PreferNoHinting：Windows 分数缩放下默认 hinting 会让中文笔画粗细不均，
    # 无提示渲染的轮廓平滑一致（Qt 高分屏标准解法）
    font = QFont("Microsoft YaHei UI", 10)
    font.setHintingPreference(QFont.PreferNoHinting)
    app.setFont(font)
    app.setStyleSheet(build_qss(DEFAULT_ZOOM, theme if theme in THEMES else DEFAULT_THEME))

    window = MainWindow()
    window.show()

    sys.exit(app.exec_())


if __name__ == '__main__':
    sys.exit(main())
