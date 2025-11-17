#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys, time, signal, os, platform
from datetime import datetime
from PyQt5.QtWidgets import *
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import QTimer, Qt
from datetime import datetime, timedelta
# === 跨平台日志路径 ===
IS_WINDOWS = platform.system() == "Windows"
LOG_DIR = os.path.expanduser("~/.config" if not IS_WINDOWS else os.getenv("APPDATA", ""))
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "timer.log")


class TrayTimer(QSystemTrayIcon):
    def __init__(self):
        super().__init__()
        super().__init__()
        # self.setIcon(self.get_icon("chronometer"))  # 必须先设置图标
        icon = self.get_icon("chronometer")
        if icon.isNull():
            icon = QIcon.fromTheme("dialog-information")  # 最终兜底
        self.setIcon(icon)
        self.setToolTip("计时器")
        self.show()  # 现在才安全

        self.mode = "stop"
        self.start_time = 0
        self.target_sec = 0
        self.blink = False
        self.event_name = ""

        menu = QMenu()
        self.a_timer = menu.addAction("正计时")
        self.a_countdown = menu.addAction("倒计时 (60 或 1:30)")
        self.a_stop = menu.addAction("停止")
        menu.addSeparator()
        self.a_quit = menu.addAction("退出")
        self.setContextMenu(menu)

        self.a_timer.triggered.connect(self.start_timer)
        self.a_countdown.triggered.connect(self.start_countdown)
        self.a_stop.triggered.connect(self.stop)
        self.a_quit.triggered.connect(qApp.quit)
        self.activated.connect(self.on_click)

        self.timer = QTimer()
        self.timer.timeout.connect(self.update)
        self.timer.start(500)

        self.blink_timer = QTimer()
        self.blink_timer.timeout.connect(self.do_blink)

    def get_icon(self, name):
        if IS_WINDOWS:
            # Windows: 使用内置图标或本地 .ico
            return QIcon.fromTheme("appointment-new") or QIcon("timer.ico")
        else:
            icon = QIcon.fromTheme(name)
            return icon if not icon.isNull() else QIcon.fromTheme("appointment")
    
    # === 记录日志 ===
    def log(self, action, duration=None):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{now}] {action}: {self.event_name}"
        if duration is not None:
            line += f" | 用时: {self.format(duration)}"
        line += "\n"
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line)

    # === 获取事件名称 ===
    def get_event_name(self):
        name, ok = QInputDialog.getText(None, "事件名称", "请输入事件名称:", text="盘坐")
        return name.strip() or "未命名任务" if ok else None

    def start_timer(self):
        name = self.get_event_name()
        if not name: return
        self.event_name = name
        self.mode = "timer"
        self.start_time = time.time()
        self.log("正计时开始")
        self.setToolTip("正计时: 0:00:00")

    def start_countdown(self):
        name = self.get_event_name()
        if not name: return
        self.event_name = name

        # === 新增：模式选择对话框 ===
        dialog = QDialog()
        dialog.setWindowTitle("倒计时设置")
        layout = QVBoxLayout()

        # 模式选择
        mode_combo = QComboBox()
        mode_combo.addItems([
            "秒数 (如 90)",
            "分钟:秒 (如 1:30)",
            "结束时间 HH:MM (如 20:00)",
            "结束时间 HH:MM:SS (如 15:10:10)"
        ])
        layout.addWidget(QLabel("选择倒计时模式:"))
        layout.addWidget(mode_combo)

        # 输入框
        input_edit = QLineEdit()
        input_edit.setPlaceholderText("请输入对应格式的值")
        layout.addWidget(QLabel("输入值:"))
        layout.addWidget(input_edit)

        # 按钮
        btn_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btn_box.accepted.connect(dialog.accept)
        btn_box.rejected.connect(dialog.reject)
        layout.addWidget(btn_box)

        dialog.setLayout(layout)

        # 动态提示
        def update_placeholder():
            idx = mode_combo.currentIndex()
            placeholders = [
                "例如: 90",
                "例如: 1:30",
                "例如: 20:00",
                "例如: 15:10:10"
            ]
            input_edit.setPlaceholderText(placeholders[idx])

        mode_combo.currentIndexChanged.connect(update_placeholder)
        update_placeholder()  # 初始

        if dialog.exec_() != QDialog.Accepted:
            return

        mode_idx = mode_combo.currentIndex()
        text = input_edit.text().strip()
        if not text:
            self.showMessage("错误", "请输入值", QSystemTrayIcon.Critical, 2000)
            return

        now = datetime.now()
        try:
            if mode_idx == 0:  # 秒数
                sec = int(text)
                if sec <= 0: raise ValueError
                self.target_sec = sec
                self.log("倒计时开始 (秒数)", sec)

            elif mode_idx == 1:  # m:s
                if ':' not in text: raise ValueError
                m, s = map(int, text.split(':'))
                sec = m * 60 + s
                if sec <= 0: raise ValueError
                self.target_sec = sec
                self.log("倒计时开始 (m:s)", sec)

            elif mode_idx == 2:  # HH:MM
                if ':' not in text: raise ValueError
                h, m = map(int, text.split(':'))
                if h > 23 or m > 59: raise ValueError
                today = now.date()
                target_time = datetime.combine(today, datetime.min.time())
                target_time = target_time.replace(hour=h, minute=m, second=0)
                if target_time <= now:
                    target_time += timedelta(days=1)
                self.target_sec = int((target_time - now).total_seconds())
                self.log("倒计时开始 (HH:MM)", self.target_sec)
                self.log(f"目标时间: {target_time.strftime('%H:%M:%S')}")

            elif mode_idx == 3:  # HH:MM:SS
                parts = list(map(int, text.split(':')))
                if len(parts) != 3: raise ValueError
                h, m, s = parts
                if h > 23 or m > 59 or s > 59: raise ValueError
                today = now.date()
                target_time = datetime.combine(today, datetime.min.time())
                target_time = target_time.replace(hour=h, minute=m, second=s)
                if target_time <= now:
                    target_time += timedelta(days=1)
                self.target_sec = int((target_time - now).total_seconds())
                self.log("倒计时开始 (HH:MM:SS)", self.target_sec)
                self.log(f"目标时间: {target_time.strftime('%H:%M:%S')}")

        except:
            self.showMessage("错误", "输入格式错误，请检查！", QSystemTrayIcon.Critical, 3000)
            return

        self.mode = "countdown"
        self.start_time = time.time()
        self.setToolTip(f"倒计时: {self.format(self.target_sec)}")


    def stop(self):
        if self.mode == "stop": return
        duration = int(time.time() - self.start_time)
        action = "正计时结束" if self.mode == "timer" else "倒计时结束"
        self.log(action, duration)
        self.mode = "stop"
        self.blink_timer.stop()
        self.setIcon(self.get_icon("chronometer"))
        self.setToolTip("计时器")

    def update(self):
        if self.mode == "timer":
            sec = int(time.time() - self.start_time)
            self.setToolTip(f"正计时: {self.format(sec)}")

        elif self.mode == "countdown":
            elapsed = int(time.time() - self.start_time)
            remain = self.target_sec - elapsed

            if remain > 0:
                self.setToolTip(f"倒计时: {self.format(remain)}")
            else:
                over = -remain
                self.setToolTip(f"已超: -{self.format(over)}")
                if not self.blink_timer.isActive():
                    self.blink_timer.start(500)
                    self.showMessage("倒计时结束", f"已超时 {over} 秒，继续计时…", QSystemTrayIcon.Warning, 3000)

        self.a_stop.setEnabled(self.mode != "stop")

    def do_blink(self):
        self.blink = not self.blink
        self.setIcon(self.get_icon("dialog-warning" if self.blink else "chronometer"))

    def on_click(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.contextMenu().popup(self.geometry().center())

    @staticmethod
    def format(sec):
        h, r = divmod(abs(sec), 3600)
        m, s = divmod(r, 60)
        sign = "-" if sec < 0 else ""
        return f"{sign}{h:02d}:{m:02d}:{s:02d}"

def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    tray = TrayTimer()
    signal.signal(signal.SIGINT, lambda *a: app.quit())
    signal.signal(signal.SIGTERM, lambda *a: app.quit())
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
