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

        # === 新增：支持结束时间输入 ===
        text, ok = QInputDialog.getText(
            None, "倒计时", 
            "输入秒数、m:s 或 结束时间 HH:MM:SS（如 15:10:10）:",
            text="60"
        )
        if not ok: return

        try:
            # 1. 尝试解析为结束时间 HH:MM:SS 或 MM:SS
            parts = text.strip().split(':')
            if len(parts) == 3:  # HH:MM:SS
                h, m, s = map(int, parts)
                target_time = datetime.now().replace(hour=h, minute=m, second=s, microsecond=0)
            elif len(parts) == 2:  # MM:SS
                m, s = map(int, parts)
                target_time = datetime.now().replace(minute=m, second=s, microsecond=0)
            else:
                raise ValueError

            # 若早于当前时间 → 视为明天
            if target_time <= datetime.now():
                target_time += timedelta(days=1)

            self.target_sec = int((target_time - datetime.now()).total_seconds())
            if self.target_sec <= 0:
                raise ValueError

            self.log("倒计时开始 (目标时间)", self.target_sec)
            self.log(f"目标时间: {target_time.strftime('%H:%M:%S')}")
        except:
            # 2. 回退：秒数或 m:s
            try:
                if ':' in text.strip():
                    m, s = map(int, text.strip().split(':'))
                    sec = m * 60 + s
                else:
                    sec = int(text.strip())
                if sec <= 0: raise ValueError
                self.target_sec = sec
                self.log("倒计时开始", sec)
            except:
                self.showMessage("错误", "格式错误！\n支持：秒数、m:s、HH:MM:SS、MM:SS", QSystemTrayIcon.Critical, 3000)
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