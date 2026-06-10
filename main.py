# -*- coding: utf-8 -*-
"""基准价得分计算器 - 程序入口

根据评标规则自动计算基准价和应答人价格得分的桌面工具。
"""

import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QFont, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QApplication

from ui.main_window import MainWindow


def _makeLogo() -> QIcon:
	"""程序化绘制应用图标"""
	pm = QPixmap(128, 128)
	pm.fill(Qt.transparent)

	painter = QPainter(pm)
	painter.setRenderHint(QPainter.Antialiasing)

	# 背景圆形
	painter.setBrush(QBrush(QColor('#4472C4')))
	painter.setPen(Qt.NoPen)
	painter.drawEllipse(8, 8, 112, 112)

	# 外环
	painter.setBrush(Qt.NoBrush)
	pen = QPen(QColor('#FFFFFF'))
	pen.setWidth(3)
	painter.setPen(pen)
	painter.drawEllipse(20, 20, 88, 88)

	# 中间 "A=B" 文字
	font = QFont('Consolas', 26, QFont.Bold)
	painter.setFont(font)
	painter.setPen(QColor('#FFFFFF'))
	painter.drawText(pm.rect(), Qt.AlignCenter, 'A≈B')

	# 底部 "80" 标签
	font2 = QFont('Consolas', 16, QFont.Bold)
	painter.setFont(font2)
	painter.drawText(pm.rect().adjusted(0, 30, 0, 0), Qt.AlignCenter, '')
	# 在靠近底部画 ¥
	painter.drawText(pm.rect().adjusted(0, 18, -38, -8), Qt.AlignRight | Qt.AlignVCenter, '')
	pen2 = QPen(QColor('#FFD700'))
	pen2.setWidth(2)
	painter.setPen(pen2)
	painter.drawLine(50, 85, 78, 85)

	# 顶部靶心点
	painter.setBrush(QBrush(QColor('#FFD700')))
	painter.setPen(Qt.NoPen)
	painter.drawEllipse(58, 28, 12, 12)

	painter.end()
	return QIcon(pm)


def main():
	app = QApplication(sys.argv)
	app.setStyle('Fusion')

	# 设置图标
	app.setWindowIcon(_makeLogo())

	# 设置默认字体
	font = QFont('微软雅黑')
	font.setPointSize(10)
	app.setFont(font)

	window = MainWindow()
	window.show()

	sys.exit(app.exec())


if __name__ == '__main__':
	main()
