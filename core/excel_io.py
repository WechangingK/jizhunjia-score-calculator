# -*- coding: utf-8 -*-
"""Excel导入导出工具

支持从Excel文件导入应答人报价数据，以及将计算结果导出为Excel文件。
"""

from typing import Dict, List

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

from core.calculator import CalcResult


class ExcelIO:
	"""Excel导入导出"""

	NAME_PATTERNS = [
		'应答人名称', '公司名称', '供应商名称', '应答人', '名称',
		'公司', '供应商', '投标人', '投标人名称', '单位名称', '单位'
	]

	PRICE_PATTERNS = [
		'不含税总价', '报价', '总价', '价格', '不含税价',
		'投标报价', '应答报价', '金额', '总报价', '不含税'
	]

	@staticmethod
	def importBidders(filePath: str) -> Dict[str, float]:
		"""从Excel文件导入应答人数据"""
		df = pd.read_excel(filePath)

		nameCol = None
		for col in df.columns:
			colStr = str(col).strip()
			for pattern in ExcelIO.NAME_PATTERNS:
				if pattern in colStr:
					nameCol = col
					break
			if nameCol is not None:
				break

		if nameCol is None:
			raise ValueError(
				f'无法识别名称列，请确保Excel包含以下列名之一：\n'
				f'{", ".join(ExcelIO.NAME_PATTERNS[:5])}'
			)

		priceCol = None
		for col in df.columns:
			colStr = str(col).strip()
			for pattern in ExcelIO.PRICE_PATTERNS:
				if pattern in colStr:
					priceCol = col
					break
			if priceCol is not None:
				break

		if priceCol is None:
			raise ValueError(
				f'无法识别报价列，请确保Excel包含以下列名之一：\n'
				f'{", ".join(ExcelIO.PRICE_PATTERNS[:5])}'
			)

		bidders = {}
		for _, row in df.iterrows():
			name = str(row[nameCol]).strip()
			price = row[priceCol]
			if not name or name.lower() == 'nan':
				continue
			try:
				price = float(price)
			except (ValueError, TypeError):
				continue
			bidders[name] = price

		if not bidders:
			raise ValueError('未读取到有效数据，请检查Excel内容')

		return bidders

	@staticmethod
	def exportResults(
		calcResult: CalcResult,
		ruleName: str,
		filePath: str
	):
		"""导出计算结果到Excel文件

		Args:
			calcResult: 完整计算结果
			ruleName: 使用的规则名称
			filePath: 导出路径
		"""
		wb = Workbook()
		ws = wb.active
		ws.title = '价格得分计算结果'

		# 样式定义
		headerFill = PatternFill(start_color='4472C4', end_color='4472C4', fill_type='solid')
		headerFont = Font(name='微软雅黑', bold=True, size=11, color='FFFFFF')
		dataFont = Font(name='微软雅黑', size=10)
		redFont = Font(name='微软雅黑', size=10, color='FF0000')
		greenFont = Font(name='微软雅黑', size=10, color='008000', bold=True)
		centerAlign = Alignment(horizontal='center', vertical='center')
		thinBorder = Border(
			left=Side(style='thin'), right=Side(style='thin'),
			top=Side(style='thin'), bottom=Side(style='thin')
		)

		rule = calcResult.rule
		limitText = f'{rule.maxPrice:,.2f} 元' if rule and rule.maxPrice > 0 else '不限价'
		fullScore = rule.fullScore if rule else 80

		# 标题行
		ws.merge_cells('A1:H1')
		titleCell = ws['A1']
		titleCell.value = '基准价得分计算结果'
		titleCell.font = Font(name='微软雅黑', bold=True, size=14)
		titleCell.alignment = Alignment(horizontal='center', vertical='center')

		ws.merge_cells('A2:H2')
		infoCell = ws['A2']
		infoCell.value = (
			f'评分规则：{ruleName}　|　'
			f'基准价：{calcResult.benchmark:,.2f} 元　|　'
			f'满分：{fullScore} 分　|　'
			f'最高限价：{limitText}　|　'
			f'有效应答人数：{calcResult.validCount}'
			+ (f'　|　排除：{calcResult.excludedCount}' if calcResult.excludedCount > 0 else '')
		)
		infoCell.font = Font(name='微软雅黑', size=10)
		infoCell.alignment = Alignment(horizontal='center', vertical='center')

		# 表头
		headers = ['排名', '应答人名称', '不含税总价', '基准价', '偏离基准价(%)',
				   f'价格得分(满分{fullScore})', '有效性', '备注']
		for colIdx, header in enumerate(headers, 1):
			cell = ws.cell(row=4, column=colIdx, value=header)
			cell.font = headerFont
			cell.fill = headerFill
			cell.alignment = centerAlign
			cell.border = thinBorder

		# 数据行
		for rowIdx, r in enumerate(calcResult.results):
			rowNum = 5 + rowIdx

			validText = '有效' if r.valid else '无效'

			if r.valid:
				rankText = str(r.rank)
				devText = r.deviation
				scoreText = r.score
				if r.deviation > 0:
					note = '高于基准价'
				elif r.deviation < 0:
					note = '低于基准价'
				else:
					note = '等于基准价'
			else:
				rankText = '—'
				devText = '—'
				scoreText = 0.0
				note = r.invalidReason

			data = [rankText, r.name, r.price, calcResult.benchmark,
					devText, scoreText, validText, note]

			isInvalid = not r.valid
			isFullScore = r.valid and r.score >= fullScore
			isZeroScore = r.valid and r.score <= 0

			for colIdx, value in enumerate(data, 1):
				cell = ws.cell(row=rowNum, column=colIdx, value=value)
				cell.font = dataFont
				cell.alignment = centerAlign
				cell.border = thinBorder

				if isInvalid:
					cell.font = redFont
				elif colIdx == 6:  # 得分列
					if isFullScore:
						cell.font = greenFont
					elif isZeroScore:
						cell.font = redFont

		# 列宽
		colWidths = [6, 20, 14, 14, 16, 16, 8, 26]
		for colIdx, width in enumerate(colWidths, 1):
			colLetter = chr(64 + colIdx)
			ws.column_dimensions[colLetter].width = width

		wb.save(filePath)
