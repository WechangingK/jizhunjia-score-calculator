# -*- coding: utf-8 -*-
"""主窗口界面

应答人报价输入、基准价得分计算、结果展示。
"""

from typing import Dict, List

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QFont
from PySide6.QtWidgets import (
	QAbstractItemView,
	QComboBox,
	QFileDialog,
	QGroupBox,
	QHBoxLayout,
	QHeaderView,
	QLabel,
	QMainWindow,
	QMessageBox,
	QPushButton,
	QSizePolicy,
	QSplitter,
	QStatusBar,
	QTableWidget,
	QTableWidgetItem,
	QToolBar,
	QVBoxLayout,
	QWidget,
)

from core.calculator import BidderResult, CoeffScheme, PriceCalculator
from core.excel_io import ExcelIO


class MainWindow(QMainWindow):
	"""基准价得分计算器主窗口"""

	def __init__(self):
		super().__init__()
		self.setWindowTitle('基准价得分计算器')
		self.resize(1100, 680)
		self.setMinimumSize(800, 500)

		self.calculator = PriceCalculator(CoeffScheme.TEXT_DESC)
		self.results: List[BidderResult] = []
		self.benchmark: float = 0.0

		self._setupToolbar()
		self._setupUI()
		self._setupStatusBar()
		self._applyStyle()

		# 初始化时添加一些空行方便输入
		self._addEmptyRows(8)

	# ==================== 工具栏 ====================

	def _setupToolbar(self):
		"""创建工具栏"""
		toolbar = QToolBar('工具栏')
		toolbar.setMovable(False)
		toolbar.setIconSize(toolbar.iconSize() * 0.8)
		self.addToolBar(toolbar)

		# 添加行按钮
		addBtn = QPushButton('➕ 添加行')
		addBtn.setToolTip('在表格末尾添加一个空行')
		addBtn.clicked.connect(self._addRow)
		toolbar.addWidget(addBtn)

		# 删除行按钮
		delBtn = QPushButton('🗑 删除选中行')
		delBtn.setToolTip('删除当前选中的行')
		delBtn.clicked.connect(self._delRow)
		toolbar.addWidget(delBtn)

		# 清空按钮
		clearBtn = QPushButton('🔄 清空')
		clearBtn.setToolTip('清空所有输入数据')
		clearBtn.clicked.connect(self._clearAll)
		toolbar.addWidget(clearBtn)

		toolbar.addSeparator()

		# 导入Excel按钮
		importBtn = QPushButton('📥 导入Excel')
		importBtn.setToolTip('从Excel文件导入应答人报价数据')
		importBtn.clicked.connect(self._importExcel)
		toolbar.addWidget(importBtn)

		# 导出Excel按钮
		exportBtn = QPushButton('📤 导出结果')
		exportBtn.setToolTip('将计算结果导出为Excel文件')
		exportBtn.clicked.connect(self._exportExcel)
		toolbar.addWidget(exportBtn)

		toolbar.addSeparator()

		# 计算按钮
		calcBtn = QPushButton('🖩 计算得分')
		calcBtn.setToolTip('根据当前报价数据计算基准价和各应答人得分')
		calcBtn.setStyleSheet(
			'QPushButton { font-weight: bold; background-color: #4472C4; color: white; '
			'padding: 6px 16px; border-radius: 4px; }'
			'QPushButton:hover { background-color: #3461A2; }'
		)
		calcBtn.clicked.connect(self._calculate)
		toolbar.addWidget(calcBtn)

		# 弹性占位，把方案选择推到右边
		spacer = QWidget()
		spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
		toolbar.addWidget(spacer)

		# 扣分方案切换
		schemeLabel = QLabel('  扣分方案：')
		toolbar.addWidget(schemeLabel)

		self.schemeCombo = QComboBox()
		self.schemeCombo.addItem('文字描述 (高扣0.6/低扣0.3)')
		self.schemeCombo.addItem('公式 (高扣0.4/低扣0.2)')
		self.schemeCombo.setToolTip('切换扣分系数方案，切换后需重新计算')
		self.schemeCombo.currentIndexChanged.connect(self._onSchemeChanged)
		toolbar.addWidget(self.schemeCombo)

	# ==================== 主界面 ====================

	def _setupUI(self):
		"""构建主界面布局"""
		centralWidget = QWidget()
		self.setCentralWidget(centralWidget)
		mainLayout = QVBoxLayout(centralWidget)
		mainLayout.setContentsMargins(8, 8, 8, 8)
		mainLayout.setSpacing(6)

		# 分割面板
		splitter = QSplitter(Qt.Horizontal)

		# ---- 左侧：输入区 ----
		inputBox = QGroupBox('📋 应答人报价（可直接双击单元格编辑）')
		inputLayout = QVBoxLayout(inputBox)
		inputLayout.setContentsMargins(4, 12, 4, 4)

		self.inputTable = QTableWidget()
		self.inputTable.setColumnCount(2)
		self.inputTable.setHorizontalHeaderLabels(['应答人名称', '不含税总价（元）'])
		self.inputTable.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
		self.inputTable.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
		self.inputTable.setSelectionBehavior(QAbstractItemView.SelectRows)
		self.inputTable.setSelectionMode(QAbstractItemView.ExtendedSelection)
		self.inputTable.setAlternatingRowColors(True)
		self.inputTable.verticalHeader().setDefaultSectionSize(28)
		inputLayout.addWidget(self.inputTable)

		splitter.addWidget(inputBox)

		# ---- 右侧：结果区 ----
		resultBox = QGroupBox('📊 计算结果')
		resultLayout = QVBoxLayout(resultBox)
		resultLayout.setContentsMargins(4, 12, 4, 4)

		self.resultTable = QTableWidget()
		self.resultTable.setColumnCount(6)
		self.resultTable.setHorizontalHeaderLabels([
			'排名', '应答人名称', '不含税总价', '偏离基准价(%)', '价格得分', '备注'
		])
		self.resultTable.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
		self.resultTable.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
		self.resultTable.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
		self.resultTable.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
		self.resultTable.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
		self.resultTable.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
		self.resultTable.setEditTriggers(QAbstractItemView.NoEditTriggers)
		self.resultTable.setSelectionBehavior(QAbstractItemView.SelectRows)
		self.resultTable.setAlternatingRowColors(True)
		self.resultTable.verticalHeader().setDefaultSectionSize(28)
		resultLayout.addWidget(self.resultTable)

		splitter.addWidget(resultBox)

		# 默认左右各占一半
		splitter.setSizes([550, 550])

		mainLayout.addWidget(splitter)

	# ==================== 状态栏 ====================

	def _setupStatusBar(self):
		"""创建状态栏"""
		self.statusBar = QStatusBar()
		self.setStatusBar(self.statusBar)

		self.statusBenchmark = QLabel('基准价：--')
		self.statusBenchmark.setFont(QFont('微软雅黑', 10))
		self.statusCount = QLabel('有效应答人数：0')
		self.statusCount.setFont(QFont('微软雅黑', 10))
		self.statusScheme = QLabel('当前方案：文字描述')
		self.statusScheme.setFont(QFont('微软雅黑', 10))

		self.statusBar.addPermanentWidget(self.statusBenchmark)
		self.statusBar.addPermanentWidget(self.statusCount)
		self.statusBar.addPermanentWidget(self.statusScheme)

	# ==================== 样式 ====================

	def _applyStyle(self):
		"""应用全局样式"""
		self.setStyleSheet("""
			QMainWindow {
				background-color: #F0F2F5;
			}
			QGroupBox {
				font-size: 13px;
				font-weight: bold;
				border: 1px solid #D0D5DD;
				border-radius: 6px;
				margin-top: 10px;
				padding-top: 18px;
				background-color: #FFFFFF;
			}
			QGroupBox::title {
				subcontrol-origin: margin;
				left: 12px;
				padding: 0 8px;
				color: #1D2939;
			}
			QTableWidget {
				gridline-color: #E8ECF0;
				font-size: 12px;
				border: none;
			}
			QTableWidget::item:selected {
				background-color: #D4E4FC;
				color: #1D2939;
			}
			QHeaderView::section {
				background-color: #F7F8FA;
				border: 1px solid #E0E4EA;
				padding: 6px 8px;
				font-weight: bold;
				font-size: 12px;
			}
			QToolBar {
				background-color: #FFFFFF;
				border-bottom: 1px solid #E0E4EA;
				padding: 4px 8px;
				spacing: 4px;
			}
			QPushButton {
				padding: 6px 12px;
				border: 1px solid #D0D5DD;
				border-radius: 4px;
				background-color: #FFFFFF;
				font-size: 12px;
			}
			QPushButton:hover {
				background-color: #F0F4FC;
				border-color: #4472C4;
			}
			QComboBox {
				padding: 4px 8px;
				border: 1px solid #D0D5DD;
				border-radius: 4px;
				font-size: 12px;
				min-width: 200px;
			}
			QStatusBar {
				background-color: #FFFFFF;
				border-top: 1px solid #E0E4EA;
				font-size: 12px;
			}
		""")

	# ==================== 数据采集 ====================

	def _collectBidders(self) -> Dict[str, float]:
		"""从输入表格收集应答人数据"""
		bidders = {}
		for row in range(self.inputTable.rowCount()):
			nameItem = self.inputTable.item(row, 0)
			priceItem = self.inputTable.item(row, 1)

			if nameItem is None or priceItem is None:
				continue

			name = nameItem.text().strip()
			if not name:
				continue

			priceText = priceItem.text().strip().replace(',', '').replace('，', '')
			if not priceText:
				continue

			try:
				price = float(priceText)
			except ValueError:
				continue

			if price < 0:
				continue

			bidders[name] = round(price, 2)

		return bidders

	# ==================== 表格操作 ====================

	def _addEmptyRows(self, count: int = 1):
		"""在表格末尾添加空行"""
		currentRow = self.inputTable.rowCount()
		self.inputTable.setRowCount(currentRow + count)

	def _addRow(self):
		"""添加一个空行"""
		self._addEmptyRows(1)
		# 滚动到新行并聚焦
		lastRow = self.inputTable.rowCount() - 1
		self.inputTable.scrollToBottom()
		self.inputTable.setCurrentCell(lastRow, 0)

	def _delRow(self):
		"""删除选中的行"""
		selectedRows = set()
		for idx in self.inputTable.selectedIndexes():
			selectedRows.add(idx.row())

		if not selectedRows:
			QMessageBox.information(self, '提示', '请先选中要删除的行')
			return

		# 从大到小删除，避免索引偏移
		for row in sorted(selectedRows, reverse=True):
			self.inputTable.removeRow(row)

	def _clearAll(self):
		"""清空所有输入数据"""
		reply = QMessageBox.question(
			self, '确认清空', '确定要清空所有输入数据吗？',
			QMessageBox.Yes | QMessageBox.No, QMessageBox.No
		)
		if reply == QMessageBox.Yes:
			self.inputTable.setRowCount(0)
			self.resultTable.setRowCount(0)
			self.results = []
			self.benchmark = 0.0
			self._updateStatus()
			self._addEmptyRows(5)

	# ==================== Excel操作 ====================

	def _importExcel(self):
		"""从Excel导入数据"""
		filePath, _ = QFileDialog.getOpenFileName(
			self, '导入Excel文件', '',
			'Excel文件 (*.xlsx *.xls);;所有文件 (*.*)'
		)
		if not filePath:
			return

		try:
			bidders = ExcelIO.importBidders(filePath)
		except Exception as e:
			QMessageBox.critical(self, '导入失败', f'读取Excel文件失败：\n{e}')
			return

		if not bidders:
			QMessageBox.warning(self, '导入失败', '未从文件中读取到有效数据')
			return

		# 填充到输入表格
		self.inputTable.setRowCount(0)
		for name, price in bidders.items():
			row = self.inputTable.rowCount()
			self.inputTable.insertRow(row)
			self.inputTable.setItem(row, 0, QTableWidgetItem(name))
			priceItem = QTableWidgetItem(f'{price:.2f}')
			priceItem.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
			self.inputTable.setItem(row, 1, priceItem)

		self.statusBar.showMessage(f'成功导入 {len(bidders)} 条数据', 3000)

	def _exportExcel(self):
		"""导出结果到Excel"""
		if not self.results:
			QMessageBox.information(self, '提示', '没有可导出的结果，请先点击"计算得分"')
			return

		filePath, _ = QFileDialog.getSaveFileName(
			self, '导出计算结果', '价格得分计算结果.xlsx',
			'Excel文件 (*.xlsx);;所有文件 (*.*)'
		)
		if not filePath:
			return

		try:
			bidderCount = len(self._collectBidders())
			ExcelIO.exportResults(
				self.results, self.benchmark, bidderCount,
				self.schemeCombo.currentText(), filePath
			)
			self.statusBar.showMessage(f'结果已导出至：{filePath}', 5000)
		except Exception as e:
			QMessageBox.critical(self, '导出失败', f'导出Excel文件失败：\n{e}')

	# ==================== 计算 ====================

	def _calculate(self):
		"""执行计算"""
		# 收集数据
		bidders = self._collectBidders()

		if len(bidders) < 1:
			QMessageBox.warning(self, '提示', '请至少输入一个应答人的报价数据')
			return

		# 更新计算器方案
		scheme = self._currentScheme()
		self.calculator.scheme = scheme

		# 计算
		prices = list(bidders.values())
		self.benchmark = self.calculator.calcBenchmark(prices)
		self.results = self.calculator.calculateAll(bidders)

		# 显示结果
		self._displayResults()
		self._updateStatus()

		self.statusBar.showMessage(
			f'计算完成！基准价：{self.benchmark:.2f}，'
			f'有效应答人数：{len(bidders)}',
			5000
		)

	def _displayResults(self):
		"""在结果表格中显示计算结果"""
		self.resultTable.setRowCount(0)

		for r in self.results:
			row = self.resultTable.rowCount()
			self.resultTable.insertRow(row)

			# 排名
			rankItem = QTableWidgetItem(str(r.rank))
			rankItem.setTextAlignment(Qt.AlignCenter)
			self.resultTable.setItem(row, 0, rankItem)

			# 名称
			nameItem = QTableWidgetItem(r.name)
			self.resultTable.setItem(row, 1, nameItem)

			# 报价
			priceItem = QTableWidgetItem(f'{r.price:,.2f}')
			priceItem.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
			self.resultTable.setItem(row, 2, priceItem)

			# 偏离百分比
			if r.deviation > 0:
				devText = f'↑ {r.deviation:.2f}%'
			elif r.deviation < 0:
				devText = f'↓ {abs(r.deviation):.2f}%'
			else:
				devText = '0.00%'
			devItem = QTableWidgetItem(devText)
			devItem.setTextAlignment(Qt.AlignCenter)
			# 颜色标记
			if r.deviation > 0:
				devItem.setForeground(Qt.red)
			elif r.deviation < 0:
				devItem.setForeground(Qt.darkGreen)
			self.resultTable.setItem(row, 3, devItem)

			# 得分
			scoreItem = QTableWidgetItem(f'{r.score:.2f}')
			scoreItem.setTextAlignment(Qt.AlignCenter)
			font = scoreItem.font()
			font.setBold(True)
			if r.score >= 80:
				font.setPointSize(font.pointSize() + 1)
				scoreItem.setForeground(Qt.darkGreen)
			elif r.score <= 0:
				scoreItem.setForeground(Qt.red)
			scoreItem.setFont(font)
			self.resultTable.setItem(row, 4, scoreItem)

			# 备注
			if r.deviation > 0:
				note = '高于基准价'
			elif r.deviation < 0:
				note = '低于基准价'
			else:
				note = '等于基准价'
			noteItem = QTableWidgetItem(note)
			noteItem.setTextAlignment(Qt.AlignCenter)
			self.resultTable.setItem(row, 5, noteItem)

	# ==================== 状态更新 ====================

	def _updateStatus(self):
		"""更新状态栏信息"""
		bidders = self._collectBidders()
		count = len(bidders)

		if self.results:
			self.statusBenchmark.setText(f'基准价：{self.benchmark:,.2f} 元')
		else:
			self.statusBenchmark.setText('基准价：--')

		self.statusCount.setText(f'有效应答人数：{count}')

		schemeName = '文字描述 (高0.6/低0.3)' if self._currentScheme() == CoeffScheme.TEXT_DESC else '公式 (高0.4/低0.2)'
		self.statusScheme.setText(f'当前方案：{schemeName}')

	# ==================== 事件处理 ====================

	def _currentScheme(self) -> CoeffScheme:
		"""获取当前选择的扣分方案"""
		if self.schemeCombo.currentIndex() == 0:
			return CoeffScheme.TEXT_DESC
		return CoeffScheme.FORMULA

	def _onSchemeChanged(self, index: int):
		"""扣分方案切换时自动重算"""
		if self.results:
			self._calculate()
