# -*- coding: utf-8 -*-
"""主窗口界面

双 Tab 模式：
- Tab 1: 价格计算（基准价法）
- Tab 2: 综合评审（8项因素全面评分+对比+建议）
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
	QLabel,
	QMainWindow,
	QStatusBar,
	QTabWidget,
	QVBoxLayout,
	QWidget,
)

from core.rule_engine import RuleManager
from ui.price_tab import PriceTab
from ui.evaluation_tab import EvaluationTab


class MainWindow(QMainWindow):
	"""基准价得分计算器 v2.1 主窗口"""

	def __init__(self):
		super().__init__()
		self.setWindowTitle('基准价得分计算器 v2.1 — 综合评审')
		self.resize(1300, 820)
		self.setMinimumSize(1000, 650)

		self.ruleManager = RuleManager.getInstance()

		self._setupUI()
		self._setupStatusBar()
		self._applyStyle()

	# ==================== UI ====================

	def _setupUI(self):
		"""构建主界面 - QTabWidget 双 Tab"""
		centralWidget = QWidget()
		self.setCentralWidget(centralWidget)
		layout = QVBoxLayout(centralWidget)
		layout.setContentsMargins(0, 0, 0, 0)
		layout.setSpacing(0)

		self.tabWidget = QTabWidget()
		self.tabWidget.setDocumentMode(True)

		# Tab 1: 价格计算（现有功能）
		self.priceTab = PriceTab()
		self.tabWidget.addTab(self.priceTab, '💰 价格计算')

		# Tab 2: 综合评审（新功能）
		self.evaluationTab = EvaluationTab()
		self.tabWidget.addTab(self.evaluationTab, '📊 综合评审')

		layout.addWidget(self.tabWidget)

	# ==================== 状态栏 ====================

	def _setupStatusBar(self):
		"""创建状态栏"""
		self.statusBar = QStatusBar()
		self.setStatusBar(self.statusBar)

		self.statusLabel = QLabel('就绪')
		self.statusLabel.setFont(QFont('微软雅黑', 10))
		self.statusBar.addWidget(self.statusLabel)

	# ==================== 样式 ====================

	def _applyStyle(self):
		"""应用全局样式"""
		self.setStyleSheet("""
			QMainWindow { background-color: #F0F2F5; }
			QTabWidget::pane {
				border: 1px solid #D0D5DD; border-radius: 4px;
				background-color: #FFFFFF;
			}
			QTabBar::tab {
				padding: 8px 20px; font-size: 14px; font-weight: bold;
				border: 1px solid #D0D5DD;
				border-bottom: none;
				border-top-left-radius: 6px; border-top-right-radius: 6px;
				margin-right: 2px;
				background-color: #E8ECF0; color: #555;
			}
			QTabBar::tab:selected {
				background-color: #FFFFFF; color: #1D2939;
				border-bottom: 2px solid #4472C4;
			}
			QTabBar::tab:hover:!selected {
				background-color: #F0F4FC; color: #4472C4;
			}
			QGroupBox {
				font-size: 13px; font-weight: bold;
				border: 1px solid #D0D5DD; border-radius: 6px;
				margin-top: 10px; padding-top: 18px;
				background-color: #FFFFFF;
			}
			QGroupBox::title {
				subcontrol-origin: margin; left: 12px;
				padding: 0 8px; color: #1D2939;
			}
			QTableWidget {
				gridline-color: #E8ECF0; font-size: 12px; border: none;
			}
			QTableWidget::item:selected {
				background-color: #D4E4FC; color: #1D2939;
			}
			QHeaderView::section {
				background-color: #F7F8FA; border: 1px solid #E0E4EA;
				padding: 6px 8px; font-weight: bold; font-size: 11px;
			}
			QPushButton {
				padding: 6px 12px; border: 1px solid #D0D5DD;
				border-radius: 4px; background-color: #FFFFFF; font-size: 12px;
			}
			QPushButton:hover { background-color: #F0F4FC; border-color: #4472C4; }
			QComboBox {
				padding: 4px 8px; border: 1px solid #D0D5DD;
				border-radius: 4px; font-size: 12px; min-width: 160px;
			}
			QStatusBar {
				background-color: #FFFFFF; border-top: 1px solid #E0E4EA; font-size: 12px;
			}
			QTextEdit {
				font-family: '微软雅黑'; font-size: 12px;
			}
		""")
