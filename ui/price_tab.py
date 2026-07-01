# -*- coding: utf-8 -*-
"""价格计算 Tab

从原 main_window 中提取的独立 Widget。
包含应答人报价输入、基准价得分计算、结果展示、规则管理。
"""

from typing import Dict, List

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
	QAbstractItemView,
	QComboBox,
	QFileDialog,
	QFrame,
	QGroupBox,
	QHBoxLayout,
	QHeaderView,
	QLabel,
	QMessageBox,
	QPushButton,
	QSizePolicy,
	QSplitter,
	QTableWidget,
	QTableWidgetItem,
	QVBoxLayout,
	QWidget,
)

from core.calculator import BidderResult, CalcResult, PriceCalculator
from core.excel_io import ExcelIO
from core.rule_engine import RuleManager
from ui.rule_dialog import RuleDialog


class PriceTab(QWidget):
	"""基准价得分计算器 - 价格计算页"""

	def __init__(self, parent=None):
		super().__init__(parent)

		self.ruleManager = RuleManager.getInstance()
		self.calcResult: CalcResult = CalcResult()
		self._lastBidders: Dict[str, float] = {}

		self._setupUI()
		self._refreshRuleCombo()
		self._addEmptyRows(8)

	# ==================== UI ====================

	def _setupUI(self):
		"""构建页面布局"""
		layout = QVBoxLayout(self)
		layout.setContentsMargins(8, 8, 8, 8)
		layout.setSpacing(6)

		# ---- 工具栏 ----
		toolLayout = QHBoxLayout()
		toolLayout.setSpacing(4)

		addBtn = QPushButton('➕ 添加行')
		addBtn.setToolTip('在表格末尾添加一个空行')
		addBtn.clicked.connect(self._addRow)
		toolLayout.addWidget(addBtn)

		delBtn = QPushButton('🗑 删除选中行')
		delBtn.setToolTip('删除当前选中的行')
		delBtn.clicked.connect(self._delRow)
		toolLayout.addWidget(delBtn)

		clearBtn = QPushButton('🔄 清空')
		clearBtn.setToolTip('清空所有输入数据')
		clearBtn.clicked.connect(self._clearAll)
		toolLayout.addWidget(clearBtn)

		toolLayout.addSpacing(8)

		importBtn = QPushButton('📥 导入Excel')
		importBtn.setToolTip('从Excel文件导入应答人报价数据')
		importBtn.clicked.connect(self._importExcel)
		toolLayout.addWidget(importBtn)

		exportBtn = QPushButton('📤 导出结果')
		exportBtn.setToolTip('将计算结果导出为Excel文件')
		exportBtn.clicked.connect(self._exportExcel)
		toolLayout.addWidget(exportBtn)

		toolLayout.addSpacing(8)

		calcBtn = QPushButton('🖩 计算得分')
		calcBtn.setToolTip('根据当前报价数据计算基准价和各应答人得分')
		calcBtn.setStyleSheet(
			'QPushButton { font-weight: bold; background-color: #4472C4; color: white; '
			'padding: 6px 16px; border-radius: 4px; }'
			'QPushButton:hover { background-color: #3461A2; }'
		)
		calcBtn.clicked.connect(self._calculate)
		toolLayout.addWidget(calcBtn)

		# 弹性占位
		spacer = QWidget()
		spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
		toolLayout.addWidget(spacer)

		# 规则选择
		ruleLabel = QLabel('评分规则：')
		toolLayout.addWidget(ruleLabel)

		self.ruleCombo = QComboBox()
		self.ruleCombo.setMinimumWidth(180)
		self.ruleCombo.setToolTip('选择评分规则，不同项目的评标办法不同')
		self.ruleCombo.currentIndexChanged[int].connect(self._onRuleChanged)
		toolLayout.addWidget(self.ruleCombo)

		manageBtn = QPushButton('📋 管理规则')
		manageBtn.setToolTip('创建、编辑、删除评分规则')
		manageBtn.clicked.connect(self._openRuleDialog)
		toolLayout.addWidget(manageBtn)

		layout.addLayout(toolLayout)

		# ---- 规则信息面板 ----
		self.ruleInfoPanel = QFrame()
		self.ruleInfoPanel.setFrameShape(QFrame.StyledPanel)
		self.ruleInfoPanel.setStyleSheet(
			'QFrame { background-color: #F0F4FC; border: 1px solid #C4D4F0; '
			'border-radius: 6px; padding: 6px 10px; }'
		)
		ruleInfoLayout = QHBoxLayout(self.ruleInfoPanel)
		ruleInfoLayout.setContentsMargins(10, 4, 10, 4)
		self.ruleInfoLabel = QLabel()
		self.ruleInfoLabel.setFont(QFont('微软雅黑', 9))
		ruleInfoLayout.addWidget(self.ruleInfoLabel)
		ruleInfoLayout.addStretch()
		layout.addWidget(self.ruleInfoPanel)

		# ---- 分割面板 ----
		splitter = QSplitter(Qt.Horizontal)

		# 左侧：输入区
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

		# 右侧：结果区
		resultBox = QGroupBox('📊 计算结果')
		resultLayout = QVBoxLayout(resultBox)
		resultLayout.setContentsMargins(4, 12, 4, 4)

		self.resultTable = QTableWidget()
		self.resultTable.setColumnCount(7)
		self.resultTable.setHorizontalHeaderLabels([
			'排名', '应答人名称', '不含税总价', '偏离基准价(%)',
			'价格得分', '有效性', '备注'
		])
		self.resultTable.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
		self.resultTable.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
		self.resultTable.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
		self.resultTable.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
		self.resultTable.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
		self.resultTable.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
		self.resultTable.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)
		self.resultTable.setEditTriggers(QAbstractItemView.NoEditTriggers)
		self.resultTable.setSelectionBehavior(QAbstractItemView.SelectRows)
		self.resultTable.setAlternatingRowColors(True)
		self.resultTable.verticalHeader().setDefaultSectionSize(28)
		resultLayout.addWidget(self.resultTable)

		splitter.addWidget(resultBox)
		splitter.setSizes([550, 650])

		layout.addWidget(splitter)

		# ---- 状态栏信息 ----
		statusLayout = QHBoxLayout()
		statusLayout.setSpacing(16)

		self.statusRuleName = QLabel('规则：--')
		self.statusRuleName.setFont(QFont('微软雅黑', 10))
		self.statusBenchmark = QLabel('基准价：--')
		self.statusBenchmark.setFont(QFont('微软雅黑', 10))
		self.statusCount = QLabel('有效：0')
		self.statusCount.setFont(QFont('微软雅黑', 10))
		self.statusExcluded = QLabel('')
		self.statusExcluded.setFont(QFont('微软雅黑', 10))
		self.statusExcluded.setStyleSheet('color: #CC0000;')

		statusLayout.addWidget(self.statusRuleName)
		statusLayout.addWidget(self.statusBenchmark)
		statusLayout.addWidget(self.statusCount)
		statusLayout.addWidget(self.statusExcluded)
		statusLayout.addStretch()

		layout.addLayout(statusLayout)

	# ==================== 规则 ====================

	def _refreshRuleCombo(self):
		"""刷新规则下拉列表"""
		self.ruleCombo.blockSignals(True)
		self.ruleCombo.clear()

		for rule in self.ruleManager.listRules():
			icon = '🔒' if rule.isPreset else '📝'
			self.ruleCombo.addItem(f'{icon} {rule.name}', rule.id)

		activeId = self.ruleManager.activeRuleId
		for i in range(self.ruleCombo.count()):
			if self.ruleCombo.itemData(i) == activeId:
				self.ruleCombo.setCurrentIndex(i)
				break

		self.ruleCombo.blockSignals(False)
		self._updateRuleInfoPanel()

	def _updateRuleInfoPanel(self):
		"""更新规则信息面板"""
		rule = self.ruleManager.getActiveRule()
		if rule:
			self.ruleInfoLabel.setText(
				f'📌 <b>{rule.name}</b>　|　满分：<b>{rule.fullScore}</b>分　|　'
				f'限价：{"不限" if rule.maxPrice == 0 else f"{rule.maxPrice:,.2f}元"}　|　'
				f'高扣：<b>{rule.highPenalty}</b>/低扣：<b>{rule.lowPenalty}</b>　|　'
				f'去极值：{" → ".join(f"≥{t.minCount}家去{t.removeHigh}高{t.removeLow}低" if t.minCount > 0 else f"其余去{t.removeHigh}高{t.removeLow}低" for t in rule.trimTiers[:3])}'
			)

	def _updateStatus(self):
		"""更新状态信息"""
		rule = self.ruleManager.getActiveRule()
		if rule:
			self.statusRuleName.setText(f'规则：{rule.name}')

		if self.calcResult.results:
			self.statusBenchmark.setText(
				f'基准价：{self.calcResult.benchmark:,.2f} 元'
			)
			self.statusCount.setText(f'有效：{self.calcResult.validCount} 人')
			if self.calcResult.excludedCount > 0:
				self.statusExcluded.setText(f'（排除：{self.calcResult.excludedCount} 人）')
			else:
				self.statusExcluded.setText('')
		else:
			self.statusBenchmark.setText('基准价：--')
			self.statusCount.setText('有效：0')
			self.statusExcluded.setText('')

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
		self.inputTable.setRowCount(self.inputTable.rowCount() + count)

	def _addRow(self):
		self._addEmptyRows(1)
		lastRow = self.inputTable.rowCount() - 1
		self.inputTable.scrollToBottom()
		self.inputTable.setCurrentCell(lastRow, 0)

	def _delRow(self):
		selectedRows = set()
		for idx in self.inputTable.selectedIndexes():
			selectedRows.add(idx.row())
		if not selectedRows:
			QMessageBox.information(self, '提示', '请先选中要删除的行')
			return
		for row in sorted(selectedRows, reverse=True):
			self.inputTable.removeRow(row)

	def _clearAll(self):
		reply = QMessageBox.question(
			self, '确认清空', '确定要清空所有输入数据吗？',
			QMessageBox.Yes | QMessageBox.No, QMessageBox.No
		)
		if reply == QMessageBox.Yes:
			self.inputTable.setRowCount(0)
			self.resultTable.setRowCount(0)
			self.calcResult = CalcResult()
			self._updateStatus()
			self._addEmptyRows(5)

	# ==================== Excel操作 ====================

	def _importExcel(self):
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

		self.inputTable.setRowCount(0)
		for name, price in bidders.items():
			row = self.inputTable.rowCount()
			self.inputTable.insertRow(row)
			self.inputTable.setItem(row, 0, QTableWidgetItem(name))
			priceItem = QTableWidgetItem(f'{price:.2f}')
			priceItem.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
			self.inputTable.setItem(row, 1, priceItem)

		QMessageBox.information(self, '导入成功', f'成功导入 {len(bidders)} 条数据')

	def _exportExcel(self):
		if not self.calcResult.results:
			QMessageBox.information(self, '提示', '没有可导出的结果，请先点击"计算得分"')
			return

		filePath, _ = QFileDialog.getSaveFileName(
			self, '导出计算结果', '价格得分计算结果.xlsx',
			'Excel文件 (*.xlsx);;所有文件 (*.*)'
		)
		if not filePath:
			return

		try:
			rule = self.ruleManager.getActiveRule()
			ExcelIO.exportResults(
				self.calcResult, rule.name, filePath
			)
			QMessageBox.information(self, '导出成功', f'结果已导出至：\n{filePath}')
		except Exception as e:
			QMessageBox.critical(self, '导出失败', f'导出Excel文件失败：\n{e}')

	# ==================== 计算 ====================

	def _calculate(self):
		bidders = self._collectBidders()
		if len(bidders) < 1:
			QMessageBox.warning(self, '提示', '请至少输入一个应答人的报价数据')
			return

		self._lastBidders = bidders
		rule = self.ruleManager.getActiveRule()
		calc = PriceCalculator(rule)
		self.calcResult = calc.calculateAll(bidders)

		self._displayResults()
		self._updateStatus()
		self._updateRuleInfoPanel()

	def _displayResults(self):
		"""在结果表格中显示计算结果"""
		self.resultTable.setRowCount(0)

		for r in self.calcResult.results:
			row = self.resultTable.rowCount()
			self.resultTable.insertRow(row)

			# 排名
			rankText = str(r.rank) if r.valid else '—'
			rankItem = QTableWidgetItem(rankText)
			rankItem.setTextAlignment(Qt.AlignCenter)
			self.resultTable.setItem(row, 0, rankItem)

			# 名称
			nameItem = QTableWidgetItem(r.name)
			if not r.valid:
				nameItem.setForeground(Qt.red)
			self.resultTable.setItem(row, 1, nameItem)

			# 报价
			priceItem = QTableWidgetItem(f'{r.price:,.2f}')
			priceItem.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
			if not r.valid:
				priceItem.setForeground(Qt.red)
			self.resultTable.setItem(row, 2, priceItem)

			# 偏离百分比
			if r.valid:
				if r.deviation > 0:
					devText = f'↑ {r.deviation:.2f}%'
				elif r.deviation < 0:
					devText = f'↓ {abs(r.deviation):.2f}%'
				else:
					devText = '0.00%'
			else:
				devText = '—'
			devItem = QTableWidgetItem(devText)
			devItem.setTextAlignment(Qt.AlignCenter)
			if r.valid:
				if r.deviation > 0:
					devItem.setForeground(Qt.red)
				elif r.deviation < 0:
					devItem.setForeground(Qt.darkGreen)
			self.resultTable.setItem(row, 3, devItem)

			# 得分
			scoreText = f'{r.score:.2f}' if r.valid else '0.00'
			scoreItem = QTableWidgetItem(scoreText)
			scoreItem.setTextAlignment(Qt.AlignCenter)
			font = scoreItem.font()
			font.setBold(True)
			if r.valid:
				if r.score >= self.ruleManager.getActiveRule().fullScore:
					font.setPointSize(font.pointSize() + 1)
					scoreItem.setForeground(Qt.darkGreen)
				elif r.score <= 0:
					scoreItem.setForeground(Qt.red)
			else:
				scoreItem.setForeground(Qt.red)
			scoreItem.setFont(font)
			self.resultTable.setItem(row, 4, scoreItem)

			# 有效性
			validText = '✅ 有效' if r.valid else '❌ 无效'
			validItem = QTableWidgetItem(validText)
			validItem.setTextAlignment(Qt.AlignCenter)
			if not r.valid:
				validItem.setForeground(Qt.red)
			self.resultTable.setItem(row, 5, validItem)

			# 备注
			if r.valid:
				if r.deviation > 0:
					note = '高于基准价'
				elif r.deviation < 0:
					note = '低于基准价'
				else:
					note = '等于基准价'
			else:
				note = r.invalidReason
			noteItem = QTableWidgetItem(note)
			noteItem.setTextAlignment(Qt.AlignCenter)
			if not r.valid:
				noteItem.setForeground(Qt.red)
			self.resultTable.setItem(row, 6, noteItem)

	# ==================== 事件 ====================

	def _onRuleChanged(self, index: int):
		"""规则切换时自动更新"""
		ruleId = self.ruleCombo.itemData(index)
		if ruleId:
			self.ruleManager.setActiveRule(ruleId)
			self._updateRuleInfoPanel()
			self._updateStatus()
			if self._lastBidders:
				self._calculate()

	def _openRuleDialog(self):
		"""打开规则管理对话框"""
		dlg = RuleDialog(self)
		dlg.exec_()
		self._refreshRuleCombo()
		if self._lastBidders:
			self._calculate()
