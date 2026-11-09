"""构建可分发目录（dist/PassSmith/）

用法：D:/DevTools/Python3.10/python build.py

流程：
  1. PyInstaller 按 passsmith.spec 打包到 dist/PassSmith/
  2. 把 config/ 与 assets/ 复制到 dist 同级，用户可直接修改（程序优先读这里）
  3. 创建空的 output/ 运行时目录
"""

import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
DIST = os.path.join(ROOT, 'dist', 'PassSmith')


def _copy_tree(name):
    """把项目下的目录复制到产物目录（覆盖旧副本）"""
    src = os.path.join(ROOT, name)
    dst = os.path.join(DIST, name)
    if not os.path.isdir(src):
        return
    if os.path.isdir(dst):
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def main():
    cmd = [sys.executable, '-m', 'PyInstaller', 'passsmith.spec', '--noconfirm',
           '--distpath', os.path.join(ROOT, 'dist'),
           '--workpath', os.path.join(ROOT, 'build')]
    print('>>> ' + ' '.join(cmd))
    ret = subprocess.call(cmd, cwd=ROOT)
    if ret != 0:
        print('!! PyInstaller 失败，退出码', ret)
        return ret

    # 资源外置：让用户能直接改弱口令/后缀，不必进 _internal
    _copy_tree('config')
    _copy_tree('assets')
    os.makedirs(os.path.join(DIST, 'output'), exist_ok=True)

    exe = os.path.join(DIST, 'PassSmith.exe' if sys.platform == 'win32' else 'PassSmith')
    size_mb = 0
    if os.path.exists(exe):
        size_mb = os.path.getsize(exe) / 1024 / 1024
    print(f'\n构建完成: {DIST}')
    print(f'  主程序: {exe} ({size_mb:.1f} MB)')
    print('  config/ 与 assets/ 已外置，可直接修改；output/ 为运行时产物目录')
    return 0


if __name__ == '__main__':
    sys.exit(main())
