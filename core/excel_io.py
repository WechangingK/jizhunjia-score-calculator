# -*- coding: utf-8 -*-
"""Excel导入导出工具

支持从Excel文件导入应答人报价数据，以及将计算结果导出为Excel文件。
"""

from typing import Dict, List

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

from core.calculator import BidderResult


class ExcelIO:
	"""Excel导入导出"""

	# 导入时自动识别为"名称"的列名（不区分大小写）
	NAME_PATTERNS = [
		'应答人名称', '公司名称', '供应商名称', '应答人', '名称',
		'公司', '供应商', '投标人', '投标人名称', '单位名称', '单位'
	]

	# 导入时自动识别为"报价"的列名（不区分大小写）
	PRICE_PATTERNS = [
		'不含税总价', '报价', '总价', '价格', '不含税价',
		'投标报价', '应答报价', '金额', '总报价', '不含税'
	]

	@staticmethod
	def importBidders(filePath: str) -> Dict[str, float]:
		"""从Excel文件导入应答人数据

		自动识别名称列和报价列。如果存在多列匹配，
		取第一个匹配列。

		Args:
			filePath: Excel文件路径 (.xlsx/.xls)

		Returns:
			{应答人名称: 不含税总价} 字典

		Raises:
			ValueError: 无法识别名称列或报价列
		"""
		df = pd.read_excel(filePath)

		# 查找名称列
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

		# 查找报价列
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

		# 读取数据
		bidders = {}
		for _, row in df.iterrows():
			name = str(row[nameCol]).strip()
			price = row[priceCol]

			# 跳过空行或无效数据
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
		results: List[BidderResult],
		benchmark: float,
		bidderCount: int,
		schemeName: str,
		filePath: str
	):
		"""导出计算结果到Excel文件

		Args:
			results: 计算结果列表
			benchmark: 基准价
			bidderCount: 有效应答人数量
			schemeName: 扣分方案名称
			filePath: 导出的Excel文件路径
		"""
		wb = Workbook()
		ws = wb.active
		ws.title = '价格得分计算结果'

		# 样式定义
		headerFont = Font(name='微软雅黑', bold=True, size=11)
		headerFill = PatternFill(start_color='4472C4', end_color='4472C4', fill_type='solid')
		headerFontWhite = Font(name='微软雅黑', bold=True, size=11, color='FFFFFF')
		dataFont = Font(name='微软雅黑', size=10)
		centerAlign = Alignment(horizontal='center', vertical='center')
		thinBorder = Border(
			left=Side(style='thin'),
			right=Side(style='thin'),
			top=Side(style='thin'),
			bottom=Side(style='thin')
		)

		# 标题行（汇总信息）
		ws.merge_cells('A1:G1')
		titleCell = ws['A1']
		titleCell.value = '基准价得分计算结果'
		titleCell.font = Font(name='微软雅黑', bold=True, size=14)
		titleCell.alignment = Alignment(horizontal='center', vertical='center')

		ws.merge_cells('A2:G2')
		infoCell = ws['A2']
		infoCell.value = (
			f'基准价：{benchmark:.2f}　|　'
			f'有效应答人数：{bidderCount}　|　'
			f'扣分方案：{schemeName}'
		)
		infoCell.font = Font(name='微软雅黑', size=10)
		infoCell.alignment = Alignment(horizontal='center', vertical='center')

		# 表头
		headers = ['排名', '应答人名称', '不含税总价', '基准价', '偏离基准价(%)', '价格得分', '备注']
		for colIdx, header in enumerate(headers, 1):
			cell = ws.cell(row=4, column=colIdx, value=header)
			cell.font = headerFontWhite
			cell.fill = headerFill
			cell.alignment = centerAlign
			cell.border = thinBorder

		# 数据行
		for rowIdx, r in enumerate(results):
			rowNum = 5 + rowIdx

			# 偏离方向
			if r.deviation > 0:
				note = '高于基准价'
			elif r.deviation < 0:
				note = '低于基准价'
			else:
				note = '等于基准价'

			data = [r.rank, r.name, r.price, benchmark, r.deviation, r.score, note]
			for colIdx, value in enumerate(data, 1):
				cell = ws.cell(row=rowNum, column=colIdx, value=value)
				cell.font = dataFont
				cell.alignment = centerAlign
				cell.border = thinBorder

				# 得分满分绿色高亮，负分红色高亮
				if colIdx == 6:  # 得分列
					if r.score >= 80:
						cell.font = Font(name='微软雅黑', size=10, color='008000', bold=True)
					elif r.score <= 0:
						cell.font = Font(name='微软雅黑', size=10, color='FF0000', bold=True)

		# 列宽调整
		colWidths = [6, 20, 14, 14, 16, 12, 14]
		for colIdx, width in enumerate(colWidths, 1):
			ws.column_dimensions[chr(64 + colIdx)].width = width if colIdx <= 7 else 12

		wb.save(filePath)
