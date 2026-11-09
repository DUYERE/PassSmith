import sys
sys.stdout.reconfigure(line_buffering=True)
sys.path.insert(0, '.')
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QApplication
app = QApplication(sys.argv)
s = QSettings("PassSmith", "PassSmith")
s.remove("ui/geometry")
font = QFont("Microsoft YaHei UI", 10)
font.setHintingPreference(QFont.PreferNoHinting)
app.setFont(font)
from ui.main_window import MainWindow
win = MainWindow()
win.show()
f = win.info_panel.fields
f['chinese_name'].setText('张三')
win.info_panel.date_checks['birthday'].setChecked(True)
win.output_panel._on_generate()
def finish():
    print('got', len(win.output_panel.all_passwords), flush=True)
    fnt = win.generate_btn.font()
    print('font ok, hinting', fnt.hintingPreference(), flush=True)
    app.quit()
QTimer.singleShot(2000, finish)
app.exec_()
print('done', flush=True)
