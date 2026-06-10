# -*- coding: utf-8 -*-
"""基准价得分计算引擎

根据评分规则计算基准价和各应答人的价格得分。
支持最高限价过滤、可配置的去极值规则、自定义满分和扣分系数。
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from core.rule_engine import ScoringRule, TrimTier


@dataclass
class BidderResult:
	"""单个应答人的计算结果"""
	name: str              # 应答人名称
	price: float           # 不含税总价
	score: float           # 价格得分
	deviation: float       # 偏离基准价百分比(正=高于基准价)
	rank: int = 0          # 排名
	valid: bool = True     # 是否有效（超限价=无效）
	invalidReason: str = ''  # 无效原因


@dataclass
class CalcResult:
	"""一次完整计算结果"""
	results: List[BidderResult] = field(default_factory=list)  # 所有应答人结果（含无效）
	validResults: List[BidderResult] = field(default_factory=list)  # 有效结果
	benchmark: float = 0.0           # 基准价A
	validCount: int = 0              # 有效应答人数量
	excludedCount: int = 0           # 被排除数量
	rule: Optional[ScoringRule] = None  # 使用的规则


class PriceCalculator:
	"""价格得分计算器

	用法:
		rule = ruleManager.getActiveRule()
		calc = PriceCalculator(rule)
		result = calc.calculateAll({'公司A': 100.0, '公司B': 110.0})
	"""

	def __init__(self, rule: ScoringRule):
		self.rule = rule

	def _filterValid(self, bidders: Dict[str, float]) -> Tuple[Dict[str, float], Dict[str, str]]:
		"""过滤有效应答人

		排除规则:
		- 超过最高限价（若设置）

		Returns:
			(有效报价字典, {被排除名称: 排除原因})
		"""
		if not bidders:
			return {}, {}

		valid = {}
		excluded = {}

		for name, price in bidders.items():
			if self.rule.maxPrice > 0 and price > self.rule.maxPrice:
				excluded[name] = f'超出最高限价 ({price:,.2f} > {self.rule.maxPrice:,.2f})'
			else:
				valid[name] = price

		return valid, excluded

	def calcBenchmark(self, validBidders: Dict[str, float]) -> float:
		"""根据规则计算基准价A

		遍历规则的去极值区间（按minCount降序），找到匹配的区间，
		应用对应的 removeHigh/removeLow。

		Args:
			validBidders: 有效应答人 {名称: 报价} 字典

		Returns:
			基准价A，保留指定位小数
		"""
		if not validBidders:
			return 0.0

		prices = list(validBidders.values())
		count = len(prices)
		tier = self.rule.getMatchedTier(count)

		sortedPrices = sorted(prices)

		start = tier.removeLow
		end = count - tier.removeHigh if tier.removeHigh > 0 else count

		if start >= end:
			# 去极值后没有剩余数据，回退到全部平均
			trimmed = sortedPrices
		else:
			trimmed = sortedPrices[start:end]

		if not trimmed:
			return 0.0

		return round(sum(trimmed) / len(trimmed), self.rule.decimals)

	def calcScore(self, price: float, benchmark: float) -> float:
		"""计算单个报价的价格得分

		- B=A 得满分
		- B>A 每高1%扣 highPenalty 分
		- B<A 每低1%扣 lowPenalty 分
		- 负分按0分计

		Args:
			price: 该应答人的报价B
			benchmark: 基准价A

		Returns:
			价格得分，保留指定位小数，最低0分
		"""
		if benchmark == 0:
			return 0.0

		if price == benchmark:
			return self.rule.fullScore

		# 偏离百分比
		deviationPct = abs(price - benchmark) / benchmark * 100

		if price > benchmark:
			coeff = self.rule.highPenalty
		else:
			coeff = self.rule.lowPenalty

		score = self.rule.fullScore - deviationPct * coeff
		return max(0.0, round(score, self.rule.decimals))

	def calculateAll(self, bidders: Dict[str, float]) -> CalcResult:
		"""批量计算所有应答人的价格得分

		Args:
			bidders: {应答人名称: 不含税总价} 字典

		Returns:
			CalcResult：含有效/无效结果、排名、基准价等
		"""
		if not bidders:
			return CalcResult(rule=self.rule)

		# 过滤
		validBidders, excluded = self._filterValid(bidders)

		# 计算基准价（仅用有效报价）
		benchmark = self.calcBenchmark(validBidders)

		# 有效应答人得分
		results = []
		for name, price in validBidders.items():
			score = self.calcScore(price, benchmark)
			if benchmark != 0:
				deviation = round((price - benchmark) / benchmark * 100, self.rule.decimals)
			else:
				deviation = 0.0
			results.append(BidderResult(
				name=name, price=price, score=score,
				deviation=deviation, valid=True,
			))

		# 被排除的应答人
		for name, price in bidders.items():
			if name in excluded:
				results.append(BidderResult(
					name=name, price=price, score=0.0,
					deviation=0.0, valid=False,
					invalidReason=excluded[name],
				))

		# 有效结果按得分降序排列
		validResults = [r for r in results if r.valid]
		validResults.sort(key=lambda r: r.score, reverse=True)

		# 计算排名（同分并列）
		rank = 1
		for i, r in enumerate(validResults):
			if i > 0 and r.score < validResults[i - 1].score:
				rank = i + 1
			r.rank = rank

		# 所有结果排序：有效按得分降序，无效放最后
		results.sort(key=lambda r: (r.valid, r.score), reverse=True)

		return CalcResult(
			results=results,
			validResults=validResults,
			benchmark=benchmark,
			validCount=len(validResults),
			excludedCount=len(excluded),
			rule=self.rule,
		)
