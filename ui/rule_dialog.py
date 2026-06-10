# -*- coding: utf-8 -*-
"""规则管理对话框

支持创建、编辑、复制、删除评分规则。
"""

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
	QAbstractItemView,
	QDialog,
	QDialogButtonBox,
	QFormLayout,
	QGroupBox,
	QHBoxLayout,
	QHeaderView,
	QLabel,
	QLineEdit,
	QListWidget,
	QListWidgetItem,
	QMessageBox,
	QPushButton,
	QSpinBox,
	QDoubleSpinBox,
	QSplitter,
	QTableWidget,
	QTableWidgetItem,
	QTextEdit,
	QVBoxLayout,
	QWidget,
)

from core.rule_engine import RuleManager, ScoringRule, TrimTier


class RuleDialog(QDialog):
	"""规则管理对话框"""

	def __init__(self, parent=None):
		super().__init__(parent)
		self.setWindowTitle('📋 评分规则管理')
		self.resize(900, 600)
		self.setMinimumSize(750, 450)

		self.ruleManager = RuleManager.getInstance()
		self.currentRule: Optional[ScoringRule] = None
		self._dirty = False  # 是否有未保存修改

		self._setupUI()
		self._refreshList()
		self._applyStyle()

	def _setupUI(self):
		"""构建布局"""
		mainLayout = QVBoxLayout(self)

		splitter = QSplitter(Qt.Horizontal)

		# ===== 左侧：规则列表 =====
		leftWidget = QWidget()
		leftLayout = QVBoxLayout(leftWidget)
		leftLayout.setContentsMargins(0, 0, 0, 0)

		leftLayout.addWidget(QLabel('规则列表'))
		self.ruleList = QListWidget()
		self.ruleList.setMinimumWidth(200)
		self.ruleList.currentRowChanged.connect(self._onRuleSelected)
		leftLayout.addWidget(self.ruleList)

		# 操作按钮
		btnLayout = QHBoxLayout()
		newBtn = QPushButton('➕ 新建')
		newBtn.clicked.connect(self._newRule)
		dupBtn = QPushButton('📄 复制')
		dupBtn.clicked.connect(self._dupRule)
		delBtn = QPushButton('🗑 删除')
		delBtn.clicked.connect(self._delRule)
		btnLayout.addWidget(newBtn)
		btnLayout.addWidget(dupBtn)
		btnLayout.addWidget(delBtn)
		leftLayout.addLayout(btnLayout)

		splitter.addWidget(leftWidget)

		# ===== 右侧：编辑表单 =====
		rightWidget = QWidget()
		rightLayout = QVBoxLayout(rightWidget)
		rightLayout.setContentsMargins(8, 0, 0, 0)

		# 基本信息
		basicGroup = QGroupBox('基本信息')
		basicForm = QFormLayout(basicGroup)

		self.nameEdit = QLineEdit()
		self.nameEdit.setPlaceholderText('请输入规则名称')
		basicForm.addRow('规则名称：', self.nameEdit)

		self.descEdit = QTextEdit()
		self.descEdit.setMaximumHeight(60)
		self.descEdit.setPlaceholderText('规则说明（选填）')
		basicForm.addRow('规则说明：', self.descEdit)

		rightLayout.addWidget(basicGroup)

		# 评分参数
		scoreGroup = QGroupBox('评分参数')
		scoreForm = QFormLayout(scoreGroup)

		self.fullScoreSpin = QDoubleSpinBox()
		self.fullScoreSpin.setRange(0, 999.99)
		self.fullScoreSpin.setDecimals(2)
		self.fullScoreSpin.setValue(80.0)
		self.fullScoreSpin.setSuffix(' 分')
		scoreForm.addRow('满分：', self.fullScoreSpin)

		self.maxPriceSpin = QDoubleSpinBox()
		self.maxPriceSpin.setRange(0, 999999999.99)
		self.maxPriceSpin.setDecimals(2)
		self.maxPriceSpin.setValue(0)
		self.maxPriceSpin.setSuffix(' 元')
		self.maxPriceSpin.setToolTip('0 = 不限价')
		self.maxPriceSpin.setSpecialValueText('不限价')
		scoreForm.addRow('最高限价：', self.maxPriceSpin)

		self.highPenaltySpin = QDoubleSpinBox()
		self.highPenaltySpin.setRange(0, 10)
		self.highPenaltySpin.setDecimals(2)
		self.highPenaltySpin.setValue(0.6)
		self.highPenaltySpin.setSingleStep(0.1)
		self.highPenaltySpin.setSuffix(' 分/每高1%')
		scoreForm.addRow('高于基准价扣分：', self.highPenaltySpin)

		self.lowPenaltySpin = QDoubleSpinBox()
		self.lowPenaltySpin.setRange(0, 10)
		self.lowPenaltySpin.setDecimals(2)
		self.lowPenaltySpin.setValue(0.3)
		self.lowPenaltySpin.setSingleStep(0.1)
		self.lowPenaltySpin.setSuffix(' 分/每低1%')
		scoreForm.addRow('低于基准价扣分：', self.lowPenaltySpin)

		self.decimalsSpin = QSpinBox()
		self.decimalsSpin.setRange(0, 4)
		self.decimalsSpin.setValue(2)
		scoreForm.addRow('保留小数位：', self.decimalsSpin)

		rightLayout.addWidget(scoreGroup)

		# 去极值区间
		trimGroup = QGroupBox('去极值规则（按最少应答人数匹配，降序排列）')
		trimLayout = QVBoxLayout(trimGroup)

		self.trimTable = QTableWidget()
		self.trimTable.setColumnCount(3)
		self.trimTable.setHorizontalHeaderLabels(['最少应答人数', '去掉最高值数量', '去掉最低值数量'])
		self.trimTable.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
		self.trimTable.setMaximumHeight(150)
		trimLayout.addWidget(self.trimTable)

		trimBtnLayout = QHBoxLayout()
		addTierBtn = QPushButton('➕ 添加区间')
		addTierBtn.clicked.connect(self._addTier)
		delTierBtn = QPushButton('🗑 删除选中区间')
		delTierBtn.clicked.connect(self._delTier)
		trimBtnLayout.addWidget(addTierBtn)
		trimBtnLayout.addWidget(delTierBtn)
		trimBtnLayout.addStretch()
		trimLayout.addLayout(trimBtnLayout)

		rightLayout.addWidget(trimGroup)
		rightLayout.addStretch()

		# 保存按钮
		saveLayout = QHBoxLayout()
		saveLayout.addStretch()
		self.saveBtn = QPushButton('💾 保存修改')
		self.saveBtn.setStyleSheet(
			'QPushButton { font-weight: bold; background-color: #4472C4; color: white; '
			'padding: 8px 20px; border-radius: 4px; }'
			'QPushButton:hover { background-color: #3461A2; }'
		)
		self.saveBtn.clicked.connect(self._saveRule)
		saveLayout.addWidget(self.saveBtn)
		rightLayout.addLayout(saveLayout)

		# 预设提示
		self.presetHint = QLabel('⚠ 内置预设规则不可修改名称，请复制后编辑')
		self.presetHint.setStyleSheet('color: #B8860B; font-size: 11px; padding: 4px 0;')
		self.presetHint.hide()
		rightLayout.addWidget(self.presetHint)

		splitter.addWidget(rightWidget)
		splitter.setSizes([250, 650])

		mainLayout.addWidget(splitter)

		# 底部关闭按钮
		closeBtn = QPushButton('关闭')
		closeBtn.clicked.connect(self.accept)
		mainLayout.addWidget(closeBtn, alignment=Qt.AlignRight)

		# 连接数据变更信号
		self.nameEdit.textChanged.connect(lambda: setattr(self, '_dirty', True))
		self.descEdit.textChanged.connect(lambda: setattr(self, '_dirty', True))

	def _applyStyle(self):
		self.setStyleSheet("""
			QGroupBox {
				font-size: 12px; font-weight: bold;
				border: 1px solid #D0D5DD; border-radius: 4px;
				margin-top: 8px; padding-top: 16px;
			}
			QGroupBox::title {
				subcontrol-origin: margin; left: 8px;
				padding: 0 4px; color: #1D2939;
			}
			QTableWidget, QListWidget {
				border: 1px solid #E0E4EA; font-size: 12px;
			}
			QLineEdit, QTextEdit, QDoubleSpinBox, QSpinBox {
				border: 1px solid #D0D5DD; border-radius: 3px;
				padding: 4px 6px; font-size: 12px;
			}
		""")

	# ==================== 列表操作 ====================

	def _refreshList(self):
		"""刷新规则列表"""
		self.ruleList.blockSignals(True)
		currentId = self.currentRule.id if self.currentRule else None
		self.ruleList.clear()

		for rule in self.ruleManager.listRules():
			label = f'🔒 {rule.name}' if rule.isPreset else f'📝 {rule.name}'
			item = QListWidgetItem(label)
			item.setData(Qt.UserRole, rule.id)
			if rule.isPreset:
				item.setToolTip('内置预设（不可删除）')
			self.ruleList.addItem(item)

		# 恢复选中
		if currentId:
			for i in range(self.ruleList.count()):
				if self.ruleList.item(i).data(Qt.UserRole) == currentId:
					self.ruleList.setCurrentRow(i)
					break
		else:
			self.ruleList.setCurrentRow(0)

		self.ruleList.blockSignals(False)

	def _onRuleSelected(self, row: int):
		"""选中规则时加载到表单"""
		if row < 0:
			return

		ruleId = self.ruleList.item(row).data(Qt.UserRole)
		rule = self.ruleManager.getRule(ruleId)
		if rule is None:
			return

		self.currentRule = rule
		self._dirty = False

		# 填充表单
		self.nameEdit.blockSignals(True)
		self.descEdit.blockSignals(True)

		self.nameEdit.setText(rule.name)
		self.descEdit.setPlainText(rule.description)
		self.fullScoreSpin.setValue(rule.fullScore)
		self.maxPriceSpin.setValue(rule.maxPrice)
		self.highPenaltySpin.setValue(rule.highPenalty)
		self.lowPenaltySpin.setValue(rule.lowPenalty)
		self.decimalsSpin.setValue(rule.decimals)

		# 预设规则名称不可改
		self.nameEdit.setReadOnly(rule.isPreset)
		self.presetHint.setVisible(rule.isPreset)

		self.nameEdit.blockSignals(False)
		self.descEdit.blockSignals(False)

		# 去极值表
		self._loadTrimTable(rule)

	def _loadTrimTable(self, rule: ScoringRule):
		"""加载去极值到表格"""
		self.trimTable.setRowCount(0)
		for t in rule.trimTiers:
			row = self.trimTable.rowCount()
			self.trimTable.insertRow(row)

			countItem = QTableWidgetItem(str(t.minCount))
			countItem.setTextAlignment(Qt.AlignCenter)
			self.trimTable.setItem(row, 0, countItem)

			highItem = QTableWidgetItem(str(t.removeHigh))
			highItem.setTextAlignment(Qt.AlignCenter)
			self.trimTable.setItem(row, 1, highItem)

			lowItem = QTableWidgetItem(str(t.removeLow))
			lowItem.setTextAlignment(Qt.AlignCenter)
			self.trimTable.setItem(row, 2, lowItem)

	# ==================== CRUD操作 ====================

	def _newRule(self):
		"""新建空白规则"""
		rule = ScoringRule()
		rule.id = ''  # RuleManager.addRule会生成id
		self.ruleManager.addRule(rule)
		self._refreshList()
		# 选中新规则
		for i in range(self.ruleList.count()):
			if self.ruleList.item(i).data(Qt.UserRole) == rule.id:
				self.ruleList.setCurrentRow(i)
				break

	def _dupRule(self):
		"""复制当前规则"""
		if self.currentRule is None:
			return
		newRule = self.ruleManager.duplicateRule(self.currentRule.id)
		if newRule:
			self._refreshList()
			for i in range(self.ruleList.count()):
				if self.ruleList.item(i).data(Qt.UserRole) == newRule.id:
					self.ruleList.setCurrentRow(i)
					break

	def _delRule(self):
		"""删除当前规则"""
		if self.currentRule is None:
			return
		if self.currentRule.isPreset:
			QMessageBox.information(self, '提示', '内置预设规则不可删除')
			return

		reply = QMessageBox.question(
			self, '确认删除',
			f'确定要删除规则「{self.currentRule.name}」吗？此操作不可撤销。',
			QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
		)
		if reply == QMessageBox.Yes:
			self.ruleManager.deleteRule(self.currentRule.id)
			self._refreshList()

	def _saveRule(self):
		"""保存表单修改到当前规则"""
		if self.currentRule is None:
			return

		rule = self.currentRule
		rule.name = self.nameEdit.text().strip() or '未命名规则'
		rule.description = self.descEdit.toPlainText().strip()
		rule.fullScore = self.fullScoreSpin.value()
		rule.maxPrice = self.maxPriceSpin.value()
		rule.highPenalty = self.highPenaltySpin.value()
		rule.lowPenalty = self.lowPenaltySpin.value()
		rule.decimals = self.decimalsSpin.value()

		# 收集去极值区间
		tiers = []
		for row in range(self.trimTable.rowCount()):
			try:
				minCount = int(self.trimTable.item(row, 0).text())
				removeHigh = int(self.trimTable.item(row, 1).text())
				removeLow = int(self.trimTable.item(row, 2).text())
				tiers.append(TrimTier(minCount, removeHigh, removeLow))
			except (ValueError, AttributeError):
				continue
		if tiers:
			tiers.sort(key=lambda t: t.minCount, reverse=True)
			rule.trimTiers = tiers

		self.ruleManager.updateRule(rule)
		self._dirty = False
		self._refreshList()
		QMessageBox.information(self, '保存成功', f'规则「{rule.name}」已保存')

	# ==================== 去极值区间编辑 ====================

	def _addTier(self):
		"""添加一个去极值区间"""
		row = self.trimTable.rowCount()
		self.trimTable.insertRow(row)
		for col, val in enumerate(['0', '0', '0']):
			item = QTableWidgetItem(val)
			item.setTextAlignment(Qt.AlignCenter)
			self.trimTable.setItem(row, col, item)

	def _delTier(self):
		"""删除选中的去极值区间"""
		selectedRows = set()
		for idx in self.trimTable.selectedIndexes():
			selectedRows.add(idx.row())
		if not selectedRows:
			QMessageBox.information(self, '提示', '请先选中要删除的区间')
			return
		if self.trimTable.rowCount() <= 1:
			QMessageBox.information(self, '提示', '至少保留一个去极值区间（兜底）')
			return
		for row in sorted(selectedRows, reverse=True):
			self.trimTable.removeRow(row)
