#!/usr/bin/env python3
"""
XDM1000 DC 電圧測定リアルタイムプロット
pyqtgraph 版

・XDM1000 を一定周期で連続測定する。
・取得した電圧値を時系列データとして保持する。
・指定時間幅のみをスクロール表示する。
"""

import logging
import sys
import time
from collections import deque

import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtWidgets

from ese774_frame import DeviceProxy
from xdm1000 import Config
import xdm1000.server_fastapi  # noqa: F401

# httpx の INFO ログを抑制する。
logging.getLogger("httpx").setLevel(logging.WARNING)

# ----------------------------------------------------------------------
# 測定設定
# ----------------------------------------------------------------------

CONFIG_FILE = "xdm1000_server1.yml"

MODE = "voltage_dc"
AUTO_RANGE = True
INTEGRATION_SPEED = "F"

# ----------------------------------------------------------------------
# 表示設定
# ----------------------------------------------------------------------

# 表示する時間幅 [s]
PLOT_WINDOW_SEC = 60.0

# 測定周期 [ms]
MEAS_INTERVAL_MSEC = 200

# Y軸設定
# True : 自動スケール
# False: Y_MIN～Y_MAX 固定
Y_AUTO_RANGE = True

Y_MIN = -1.0e-3
Y_MAX = 1.0e-3


def create_dmm():
    """
    XDM1000 を初期化する。
    """

    config = Config(CONFIG_FILE)

    dmm = DeviceProxy(
        "Xdm1000Ctrl",
        config=config,
        async_mode=False,
    )

    dmm.set_mode(MODE)
    dmm.set_auto_range(AUTO_RANGE)
    dmm.set_integration_speed(INTEGRATION_SPEED)

    return dmm


class RealtimePlot:
    """
    リアルタイム波形表示クラス。

    QTimer により一定周期で測定を実行し、
    最新 PLOT_WINDOW_SEC 秒分のみを表示する。
    """

    def __init__(self):
        # 測定器を初期化する。
        self.dmm = create_dmm()

        # 測定開始時刻
        self.t0 = time.time()

        # 時刻・電圧データ
        self.t_values = deque()
        self.v_values = deque()

        # QApplication を生成する。
        self.app = QtWidgets.QApplication.instance()
        if self.app is None:
            self.app = QtWidgets.QApplication(sys.argv)

        # メインウィンドウ
        self.win = pg.GraphicsLayoutWidget(show=True)
        self.win.setWindowTitle("XDM1000 DC voltage waveform")

        # 波形表示
        self.plot = self.win.addPlot(title="XDM1000 DC voltage waveform")
        self.plot.setLabel("bottom", "Time", units="s")
        self.plot.setLabel("left", "Voltage", units="V")
        self.plot.showGrid(x=True, y=True)

        # 波形
        self.curve = self.plot.plot(
            [],
            [],
            pen=pg.mkPen(width=2),
            symbol="o",
            symbolSize=4,
        )

        # 初期表示範囲
        self.plot.setXRange(0.0, PLOT_WINDOW_SEC)

        if not Y_AUTO_RANGE:
            self.plot.setYRange(Y_MIN, Y_MAX)

        # 一定周期で update() を呼び出す。
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update)
        self.timer.start(MEAS_INTERVAL_MSEC)

    def update(self):
        """
        1回測定し、波形を更新する。
        """

        # 測定
        result = self.dmm.meas()

        # 現在時刻
        t = time.time() - self.t0

        # 電圧値
        v = float(result["value"])

        # データ追加
        self.t_values.append(t)
        self.v_values.append(v)

        # 表示時間を超えた古いデータを削除する。
        while self.t_values and (t - self.t_values[0]) > PLOT_WINDOW_SEC:
            self.t_values.popleft()
            self.v_values.popleft()

        # 波形更新
        self.curve.setData(
            list(self.t_values),
            list(self.v_values),
        )

        # X軸をスクロールさせる。
        x_min = max(0.0, t - PLOT_WINDOW_SEC)
        x_max = x_min + PLOT_WINDOW_SEC
        self.plot.setXRange(x_min, x_max, padding=0.0)

        # Y軸設定
        if Y_AUTO_RANGE:
            self.plot.enableAutoRange(axis="y", enable=True)
        else:
            self.plot.setYRange(Y_MIN, Y_MAX, padding=0.0)

        # コンソールにも測定値を表示する。
        print("{:.10g}".format(v), flush=True)

    def run(self):
        """
        GUI イベントループを開始する。
        """
        self.app.exec()


def main():
    """
    エントリーポイント。
    """
    plotter = RealtimePlot()
    plotter.run()


if __name__ == "__main__":
    main()
