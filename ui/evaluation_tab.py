# -*- coding: utf-8 -*-
"""综合评审 Tab

供应商综合数据输入、8项因素自动评分、横向对比、智能建议。
"""

from typing import Dict, List

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
	QAbstractItemView,
	QCheckBox,
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
	QTextEdit,
	QVBoxLayout,
	QWidget,
)

from core.comparison_engine import ComparisonEngine, ComparisonReport
from core.evaluation_factors import FactorRegistry
from core.excel_io import ExcelIO
from core.rule_engine import RuleManager
from core.supplier_scorer import SupplierInput, SupplierResult, SupplierScorer


class EvaluationTab(QWidget):
	"""综合评审页"""

	# 输入表格列索引
	COL_NAME = 0
	COL_CONTRACT = 1
	COL_TEAM = 2
	COL_FAULT = 3
	COL_SERVICE = 4
	COL_QUALITY = 5
	COL_EMERGENCY = 6
	COL_RESTRICTED = 7
	COL_PRICE = 8

	COL_COUNT = 9

	def __init__(self, parent=None):
		super().__init__(parent)

		self.ruleManager = RuleManager.getInstance()
		self.registry = FactorRegistry()
		self.scorer = SupplierScorer(self.ruleManager, self.registry)
		self.engine = ComparisonEngine(self.registry)
		self._lastResults: List[SupplierResult] = []

		self._setupUI()
		self._addEmptyRows(5)

	# ==================== UI ====================

	def _setupUI(self):
		"""构建综合评审页面布局"""
		layout = QVBoxLayout(self)
		layout.setContentsMargins(8, 8, 8, 8)
		layout.setSpacing(6)

		# ---- 工具栏 ----
		toolLayout = QHBoxLayout()
		toolLayout.setSpacing(4)

		addBtn = QPushButton('➕ 添加供应商')
		addBtn.setToolTip('在表格末尾添加一个空行')
		addBtn.clicked.connect(self._addRow)
		toolLayout.addWidget(addBtn)

		delBtn = QPushButton('🗑 删除选中')
		delBtn.setToolTip('删除当前选中的供应商行')
		delBtn.clicked.connect(self._delRow)
		toolLayout.addWidget(delBtn)

		clearBtn = QPushButton('🔄 清空')
		clearBtn.setToolTip('清空所有输入数据')
		clearBtn.clicked.connect(self._clearAll)
		toolLayout.addWidget(clearBtn)

		toolLayout.addSpacing(8)

		importBtn = QPushButton('📥 导入Excel')
		importBtn.setToolTip('从Excel文件导入供应商综合数据')
		importBtn.clicked.connect(self._importExcel)
		toolLayout.addWidget(importBtn)

		exportBtn = QPushButton('📤 导出结果')
		exportBtn.setToolTip('将综合评审结果导出为Excel文件')
		exportBtn.clicked.connect(self._exportExcel)
		toolLayout.addWidget(exportBtn)

		toolLayout.addSpacing(8)

		self.priceRuleLabel = QLabel('价格规则：')
		toolLayout.addWidget(self.priceRuleLabel)

		self.priceRuleCombo = QComboBox()
		self.priceRuleCombo.setMinimumWidth(160)
		self.priceRuleCombo.setToolTip('选择价格评分规则')
		self.priceRuleCombo.currentIndexChanged[int].connect(self._onPriceRuleChanged)
		toolLayout.addWidget(self.priceRuleCombo)

		self._refreshPriceRuleCombo()

		toolLayout.addSpacing(8)

		calcBtn = QPushButton('🖩 计算综合得分')
		calcBtn.setToolTip('根据全部8项因素计算综合得分并进行对比分析')
		calcBtn.setStyleSheet(
			'QPushButton { font-weight: bold; background-color: #4472C4; color: white; '
			'padding: 6px 16px; border-radius: 4px; }'
			'QPushButton:hover { background-color: #3461A2; }'
		)
		calcBtn.clicked.connect(self._calculate)
		toolLayout.addWidget(calcBtn)

		toolLayout.addStretch()

		layout.addLayout(toolLayout)

		# ---- 输入区 ----
		inputBox = QGroupBox('📋 供应商综合数据输入（可直接双击单元格编辑）')
		inputBoxLayout = QVBoxLayout(inputBox)
		inputBoxLayout.setContentsMargins(4, 12, 4, 4)

		self.inputTable = QTableWidget()
		self.inputTable.setColumnCount(self.COL_COUNT)
		self.inputTable.setHorizontalHeaderLabels([
			'供应商名称', '类似项目\n业绩(份)', '团队人员\n(人)',
			'故障处理\n时限(h)', '整体服务\n方案(0-3)',
			'质量控制\n方案(0-3)', '应急响应\n方案(0-3)',
			'是否限制型\n供应商', '不含税总价\n（元）'
		])
		header = self.inputTable.horizontalHeader()
		header.setSectionResizeMode(self.COL_NAME, QHeaderView.Stretch)
		for col in range(1, self.COL_COUNT):
			header.setSectionResizeMode(col, QHeaderView.ResizeToContents)
		# 确保列宽足够
		self.inputTable.setColumnWidth(self.COL_CONTRACT, 80)
		self.inputTable.setColumnWidth(self.COL_TEAM, 70)
		self.inputTable.setColumnWidth(self.COL_FAULT, 80)
		self.inputTable.setColumnWidth(self.COL_SERVICE, 80)
		self.inputTable.setColumnWidth(self.COL_QUALITY, 80)
		self.inputTable.setColumnWidth(self.COL_EMERGENCY, 80)
		self.inputTable.setColumnWidth(self.COL_RESTRICTED, 90)
		self.inputTable.setColumnWidth(self.COL_PRICE, 120)

		self.inputTable.setSelectionBehavior(QAbstractItemView.SelectRows)
		self.inputTable.setSelectionMode(QAbstractItemView.ExtendedSelection)
		self.inputTable.setAlternatingRowColors(True)
		self.inputTable.verticalHeader().setDefaultSectionSize(30)
		inputBoxLayout.addWidget(self.inputTable)

		# 提示
		hintLabel = QLabel(
			'💡 提示：序号1(业绩)填合同份数；序号2(团队)填合格人数；序号3(故障)填承诺小时数（≤8）；'
			'序号4-6填0~3分（由专家评定）；序号7勾选复选框；序号8填不含税报价'
		)
		hintLabel.setFont(QFont('微软雅黑', 8))
		hintLabel.setStyleSheet('color: #888; padding: 2px 4px;')
		inputBoxLayout.addWidget(hintLabel)

		layout.addWidget(inputBox)

		# ---- 结果区 ----
		resultSplitter = QSplitter(Qt.Vertical)

		# 结果表格
		resultBox = QGroupBox('📊 综合评分结果')
		resultBoxLayout = QVBoxLayout(resultBox)
		resultBoxLayout.setContentsMargins(4, 12, 4, 4)

		self.resultTable = QTableWidget()
		self.resultTable.setColumnCount(9)
		self.resultTable.setHorizontalHeaderLabels([
			'排名', '供应商名称', '商务(8)', '技术(8)', '服务(9)',
			'扣分', '价格(75)', '**总分(100)**', '备注'
		])
		rheader = self.resultTable.horizontalHeader()
		rheader.setSectionResizeMode(0, QHeaderView.ResizeToContents)
		rheader.setSectionResizeMode(1, QHeaderView.Stretch)
		for col in range(2, 9):
			rheader.setSectionResizeMode(col, QHeaderView.ResizeToContents)
		self.resultTable.setEditTriggers(QAbstractItemView.NoEditTriggers)
		self.resultTable.setSelectionBehavior(QAbstractItemView.SelectRows)
		self.resultTable.setAlternatingRowColors(True)
		self.resultTable.verticalHeader().setDefaultSectionSize(28)
		resultBoxLayout.addWidget(self.resultTable)

		resultSplitter.addWidget(resultBox)

		# 建议区
		adviceBox = QGroupBox('💡 智能分析与建议')
		adviceLayout = QVBoxLayout(adviceBox)
		adviceLayout.setContentsMargins(4, 12, 4, 4)

		self.adviceText = QTextEdit()
		self.adviceText.setReadOnly(True)
		self.adviceText.setMinimumHeight(140)
		self.adviceText.setStyleSheet(
			'QTextEdit { background-color: #FAFBFC; border: 1px solid #E0E4EA; '
			'border-radius: 4px; font-size: 12px; padding: 8px; }'
		)
		adviceLayout.addWidget(self.adviceText)

		resultSplitter.addWidget(adviceBox)
		resultSplitter.setSizes([300, 200])

		layout.addWidget(resultSplitter)

	# ==================== 规则 ====================

	def _refreshPriceRuleCombo(self):
		"""刷新价格规则下拉"""
		self.priceRuleCombo.blockSignals(True)
		self.priceRuleCombo.clear()

		for rule in self.ruleManager.listRules():
			icon = '🔒' if rule.isPreset else '📝'
			self.priceRuleCombo.addItem(f'{icon} {rule.name}', rule.id)

		activeId = self.ruleManager.activeRuleId
		for i in range(self.priceRuleCombo.count()):
			if self.priceRuleCombo.itemData(i) == activeId:
				self.priceRuleCombo.setCurrentIndex(i)
				break

		self.priceRuleCombo.blockSignals(False)

	# ==================== 数据采集 ====================

	def _collectSuppliers(self) -> List[SupplierInput]:
		"""从输入表格收集供应商数据"""
		suppliers = []
		for row in range(self.inputTable.rowCount()):
			nameItem = self.inputTable.item(row, self.COL_NAME)
			if nameItem is None:
				continue
			name = nameItem.text().strip()
			if not name:
				continue

			supplier = SupplierInput(name=name)

			# 序号1: 业绩数量
			supplier.contractCount = self._getIntValue(row, self.COL_CONTRACT)

			# 序号2: 团队人数
			supplier.teamCount = self._getIntValue(row, self.COL_TEAM)

			# 序号3: 故障处理时限
			supplier.faultHours = self._getFloatValue(row, self.COL_FAULT, 8.0)

			# 序号4-6: 方案得分
			supplier.servicePlanScore = self._getFloatValue(row, self.COL_SERVICE, 0.0)
			supplier.qualityPlanScore = self._getFloatValue(row, self.COL_QUALITY, 0.0)
			supplier.emergencyPlanScore = self._getFloatValue(row, self.COL_EMERGENCY, 0.0)

			# 序号7: 限制型供应商
			supplier.isRestricted = self._getBoolValue(row, self.COL_RESTRICTED)

			# 序号8: 报价
			supplier.price = self._getFloatValue(row, self.COL_PRICE, 0.0)

			suppliers.append(supplier)

		return suppliers

	def _getIntValue(self, row: int, col: int) -> int:
		"""获取整数单元格值"""
		item = self.inputTable.item(row, col)
		if item is None:
			return 0
		text = item.text().strip()
		if not text:
			return 0
		try:
			return int(float(text))
		except ValueError:
			return 0

	def _getFloatValue(self, row: int, col: int, default: float = 0.0) -> float:
		"""获取浮点单元格值"""
		item = self.inputTable.item(row, col)
		if item is None:
			return default
		text = item.text().strip().replace(',', '').replace('，', '')
		if not text:
			return default
		try:
			return float(text)
		except ValueError:
			return default

	def _getBoolValue(self, row: int, col: int) -> bool:
		"""获取布尔单元格值（从复选框组件）"""
		widget = self.inputTable.cellWidget(row, col)
		if widget is None:
			return False
		cb = widget.findChild(QCheckBox)
		if cb:
			return cb.isChecked()
		return False

	# ==================== 表格操作 ====================

	def _addEmptyRows(self, count: int = 1):
		"""添加空行"""
		startRow = self.inputTable.rowCount()
		self.inputTable.setRowCount(startRow + count)
		for row in range(startRow, startRow + count):
			# 序号7列放复选框
			cbWidget = QWidget()
			cbLayout = QHBoxLayout(cbWidget)
			cbLayout.setContentsMargins(0, 0, 0, 0)
			cbLayout.setAlignment(Qt.AlignCenter)
			cb = QCheckBox()
			cbLayout.addWidget(cb)
			self.inputTable.setCellWidget(row, self.COL_RESTRICTED, cbWidget)

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
			self.adviceText.clear()
			self._lastResults = []
			self._addEmptyRows(5)

	# ==================== Excel ====================

	def _importExcel(self):
		filePath, _ = QFileDialog.getOpenFileName(
			self, '导入Excel文件', '',
			'Excel文件 (*.xlsx *.xls);;所有文件 (*.*)'
		)
		if not filePath:
			return

		try:
			suppliers = ExcelIO.importEvaluationData(filePath)
		except Exception as e:
			QMessageBox.critical(self, '导入失败', f'读取Excel文件失败：\n{e}')
			return

		if not suppliers:
			QMessageBox.warning(self, '导入失败', '未从文件中读取到有效数据')
			return

		self.inputTable.setRowCount(0)
		for supplier in suppliers:
			self._addSupplierRow(supplier)
		QMessageBox.information(self, '导入成功', f'成功导入 {len(suppliers)} 条供应商数据')

	def _addSupplierRow(self, supplier: SupplierInput):
		"""添加一行供应商数据"""
		row = self.inputTable.rowCount()
		self.inputTable.insertRow(row)

		self.inputTable.setItem(row, self.COL_NAME, QTableWidgetItem(supplier.name))
		self.inputTable.setItem(row, self.COL_CONTRACT, QTableWidgetItem(str(supplier.contractCount)))
		self.inputTable.setItem(row, self.COL_TEAM, QTableWidgetItem(str(supplier.teamCount)))
		self.inputTable.setItem(row, self.COL_FAULT, QTableWidgetItem(str(supplier.faultHours)))
		self.inputTable.setItem(row, self.COL_SERVICE, QTableWidgetItem(str(supplier.servicePlanScore)))
		self.inputTable.setItem(row, self.COL_QUALITY, QTableWidgetItem(str(supplier.qualityPlanScore)))
		self.inputTable.setItem(row, self.COL_EMERGENCY, QTableWidgetItem(str(supplier.emergencyPlanScore)))

		# 复选框
		cbWidget = QWidget()
		cbLayout = QHBoxLayout(cbWidget)
		cbLayout.setContentsMargins(0, 0, 0, 0)
		cbLayout.setAlignment(Qt.AlignCenter)
		cb = QCheckBox()
		cb.setChecked(supplier.isRestricted)
		cbLayout.addWidget(cb)
		self.inputTable.setCellWidget(row, self.COL_RESTRICTED, cbWidget)

		priceItem = QTableWidgetItem(f'{supplier.price:.2f}')
		priceItem.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
		self.inputTable.setItem(row, self.COL_PRICE, priceItem)

	def _exportExcel(self):
		if not self._lastResults:
			QMessageBox.information(self, '提示', '没有可导出的结果，请先点击"计算综合得分"')
			return

		filePath, _ = QFileDialog.getSaveFileName(
			self, '导出综合评审结果', '综合评审计算结果.xlsx',
			'Excel文件 (*.xlsx);;所有文件 (*.*)'
		)
		if not filePath:
			return

		try:
			report = self.engine.generate(self._lastResults)
			ruleName = self.ruleManager.getActiveRule().name
			ExcelIO.exportEvaluationResults(report, ruleName, filePath)
			QMessageBox.information(self, '导出成功', f'结果已导出至：\n{filePath}')
		except Exception as e:
			QMessageBox.critical(self, '导出失败', f'导出Excel文件失败：\n{e}')

	# ==================== 计算 ====================

	def _calculate(self):
		"""执行综合评分计算"""
		suppliers = self._collectSuppliers()
		if len(suppliers) < 1:
			QMessageBox.warning(self, '提示', '请至少输入一个供应商的数据')
			return

		# 检查是否至少输入了报价
		hasPrice = any(s.price > 0 for s in suppliers)
		if not hasPrice:
			QMessageBox.warning(self, '提示', '请至少输入一个供应商的报价')
			return

		self._lastResults = self.scorer.scoreAll(suppliers)
		self._displayResults()
		self._displayAdvice()

	def _displayResults(self):
		"""在结果表格中显示综合评分结果"""
		self.resultTable.setRowCount(0)

		for r in self._lastResults:
			row = self.resultTable.rowCount()
			self.resultTable.insertRow(row)

			# 排名
			rankItem = QTableWidgetItem(str(r.rank))
			rankItem.setTextAlignment(Qt.AlignCenter)
			font = rankItem.font()
			font.setBold(True)
			if r.rank == 1:
				font.setPointSize(font.pointSize() + 2)
				rankItem.setForeground(Qt.darkYellow)
			rankItem.setFont(font)
			self.resultTable.setItem(row, 0, rankItem)

			# 名称
			nameItem = QTableWidgetItem(r.name)
			self.resultTable.setItem(row, 1, nameItem)

			# 商务得分
			commItem = QTableWidgetItem(f'{r.commercialScore:.1f}')
			commItem.setTextAlignment(Qt.AlignCenter)
			self.resultTable.setItem(row, 2, commItem)

			# 技术得分
			techItem = QTableWidgetItem(f'{r.technicalScore:.1f}')
			techItem.setTextAlignment(Qt.AlignCenter)
			self.resultTable.setItem(row, 3, techItem)

			# 服务得分
			servItem = QTableWidgetItem(f'{r.serviceScore:.1f}')
			servItem.setTextAlignment(Qt.AlignCenter)
			self.resultTable.setItem(row, 4, servItem)

			# 扣分
			dedItem = QTableWidgetItem(f'{r.deduction:.0f}' if r.deduction < 0 else '0')
			dedItem.setTextAlignment(Qt.AlignCenter)
			if r.deduction < 0:
				dedItem.setForeground(Qt.red)
				font = dedItem.font()
				font.setBold(True)
				dedItem.setFont(font)
			self.resultTable.setItem(row, 5, dedItem)

			# 价格得分
			priceItem = QTableWidgetItem(f'{r.priceScore:.2f}')
			priceItem.setTextAlignment(Qt.AlignCenter)
			if r.valid:
				if r.priceScore >= self.registry.getFactor(8).maxScore * 0.95:
					priceItem.setForeground(Qt.darkGreen)
				elif r.priceScore <= 0:
					priceItem.setForeground(Qt.red)
			else:
				priceItem.setForeground(Qt.red)
			self.resultTable.setItem(row, 6, priceItem)

			# 总分 - 高亮
			totalItem = QTableWidgetItem(f'{r.totalScore:.2f}')
			totalItem.setTextAlignment(Qt.AlignCenter)
			totalFont = totalItem.font()
			totalFont.setBold(True)
			totalFont.setPointSize(totalFont.pointSize() + 1)
			totalItem.setFont(totalFont)
			if r.rank == 1:
				totalItem.setForeground(Qt.darkGreen)
			elif r.totalScore < 60:
				totalItem.setForeground(Qt.red)
			self.resultTable.setItem(row, 7, totalItem)

			# 备注
			if not r.valid:
				note = f'价格无效: {r.invalidReason}'
				noteColor = Qt.red
			elif r.rank == 1:
				note = '🥇 综合最优'
				noteColor = Qt.darkGreen
			else:
				gap = round(self._lastResults[0].totalScore - r.totalScore, 2)
				note = f'距第1名差{gap}分'
				noteColor = Qt.darkGray
			noteItem = QTableWidgetItem(note)
			noteItem.setTextAlignment(Qt.AlignCenter)
			noteItem.setForeground(noteColor)
			self.resultTable.setItem(row, 8, noteItem)

	def _displayAdvice(self):
		"""显示智能分析建议"""
		report = self.engine.generate(self._lastResults)

		html = '<div style="font-family: 微软雅黑; font-size: 13px; line-height: 1.6;">'

		# 总体摘要
		html += f'<p style="margin: 4px 0;"><b>📊 总体概况</b></p>'
		html += f'<p style="margin: 2px 0 8px 0; color: #333;">{report.summary}</p>'

		# 整体建议
		if report.recommendations:
			html += '<p style="margin: 4px 0;"><b>🎯 综合建议</b></p>'
			for rec in report.recommendations:
				html += f'<p style="margin: 2px 0 2px 12px; color: #4472C4;">• {rec}</p>'

		# 逐家分析
		html += '<p style="margin: 8px 0 4px 0;"><b>📋 逐家分析</b></p>'
		for name, analysis in report.analysisBySupplier.items():
			# 把换行转为 <br>
			text = analysis.replace('\n', '<br>')
			html += (
				f'<div style="margin: 4px 0 8px 8px; padding: 8px; '
				f'background-color: #F7F8FA; border-radius: 4px; '
				f'border-left: 3px solid #4472C4;">{text}</div>'
			)

		html += '</div>'
		self.adviceText.setHtml(html)

	# ==================== 事件 ====================

	def _onPriceRuleChanged(self, index: int):
		ruleId = self.priceRuleCombo.itemData(index)
		if ruleId:
			self.ruleManager.setActiveRule(ruleId)
			if self._lastResults:
				self._calculate()
