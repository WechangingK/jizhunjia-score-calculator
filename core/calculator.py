# -*- coding: utf-8 -*-
"""基准价得分计算引擎

实现评标规则中的基准价计算和价格得分计算逻辑。
支持两套扣分系数方案切换。
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List


class CoeffScheme(Enum):
	"""扣分系数方案"""
	TEXT_DESC = 'text'    # 文字描述: 高扣0.6/低扣0.3
	FORMULA = 'formula'   # 公式: 高扣0.4/低扣0.2


@dataclass
class BidderResult:
	"""单个应答人的计算结果"""
	name: str              # 应答人名称
	price: float           # 不含税总价
	score: float           # 价格得分
	deviation: float       # 偏离基准价百分比(正=高于基准价)
	rank: int = 0          # 排名


class PriceCalculator:
	"""价格得分计算器

	用法:
		calc = PriceCalculator(CoeffScheme.TEXT_DESC)
		results = calc.calculateAll({'公司A': 100.0, '公司B': 110.0})
	"""

	# 扣分系数配置
	COEFF = {
		CoeffScheme.TEXT_DESC: {'high': 0.6, 'low': 0.3},
		CoeffScheme.FORMULA: {'high': 0.4, 'low': 0.2},
	}

	def __init__(self, scheme: CoeffScheme = CoeffScheme.TEXT_DESC):
		self.scheme = scheme

	@property
	def highCoeff(self) -> float:
		"""高于基准价时每1%的扣分系数"""
		return self.COEFF[self.scheme]['high']

	@property
	def lowCoeff(self) -> float:
		"""低于基准价时每1%的扣分系数"""
		return self.COEFF[self.scheme]['low']

	def calcBenchmark(self, prices: List[float]) -> float:
		"""根据规则计算基准价A

		规则:
		- >=10家: 去掉2个最高值和2个最低值，剩余求算术平均
		- 5~9家:  去掉1个最高值和1个最低值，剩余求算术平均
		- <5家:   全部报价求算术平均

		Args:
			prices: 所有有效应答人的报价列表

		Returns:
			基准价A，保留两位小数
		"""
		if not prices:
			return 0.0

		n = len(prices)
		sortedPrices = sorted(prices)

		if n >= 10:
			trimmed = sortedPrices[2:-2] if n > 4 else sortedPrices
		elif n >= 5:
			trimmed = sortedPrices[1:-1] if n > 2 else sortedPrices
		else:
			trimmed = sortedPrices

		if not trimmed:
			return 0.0

		return round(sum(trimmed) / len(trimmed), 2)

	def calcScore(self, price: float, benchmark: float) -> float:
		"""计算单个报价的价格得分

		规则:
		- B=A 得满分80分
		- B>A 每高1%扣对应系数分
		- B<A 每低1%扣对应系数分
		- 负分按0分计

		Args:
			price: 该应答人的报价B
			benchmark: 基准价A

		Returns:
			价格得分，保留两位小数，最低0分
		"""
		if benchmark == 0:
			return 0.0

		if price == benchmark:
			return 80.0

		# 偏离百分比
		deviationPct = abs(price - benchmark) / benchmark * 100

		if price > benchmark:
			coeff = self.highCoeff
		else:
			coeff = self.lowCoeff

		score = 80 - deviationPct * coeff
		return max(0.0, round(score, 2))

	def calculateAll(self, bidders: Dict[str, float]) -> List[BidderResult]:
		"""批量计算所有应答人的价格得分

		Args:
			bidders: {应答人名称: 不含税总价} 字典

		Returns:
			BidderResult列表，按得分降序排列，含排名
		"""
		if not bidders:
			return []

		prices = list(bidders.values())
		benchmark = self.calcBenchmark(prices)

		results = []
		for name, price in bidders.items():
			score = self.calcScore(price, benchmark)
			if benchmark != 0:
				deviation = round((price - benchmark) / benchmark * 100, 2)
			else:
				deviation = 0.0
			results.append(BidderResult(
				name=name,
				price=price,
				score=score,
				deviation=deviation
			))

		# 按得分降序排列
		results.sort(key=lambda r: r.score, reverse=True)

		# 计算排名（同分并列）
		rank = 1
		for i, r in enumerate(results):
			if i > 0 and r.score < results[i - 1].score:
				rank = i + 1
			r.rank = rank

		return results
