# -*- coding: utf-8 -*-
"""对比与建议引擎

对多家供应商的综合评分结果进行横向对比分析，
生成排名、对比表格和智能建议。
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from core.evaluation_factors import FactorRegistry
from core.supplier_scorer import SupplierResult


@dataclass
class ComparisonReport:
	"""对比分析报告"""
	results: List[SupplierResult] = field(default_factory=list)   # 评分结果（已排序）
	winner: Optional[SupplierResult] = None                       # 第一名
	summary: str = ''                                               # 总体分析文字
	recommendations: List[str] = field(default_factory=list)       # 整体建议
	analysisBySupplier: Dict[str, str] = field(default_factory=dict)  # {供应商名: 逐家分析文字}


class ComparisonEngine:
	"""对比分析引擎

	用法:
		engine = ComparisonEngine(registry)
		report = engine.generate(results)
	"""

	def __init__(self, factorRegistry: FactorRegistry):
		self.registry = factorRegistry

	def generate(self, results: List[SupplierResult]) -> ComparisonReport:
		"""根据评分结果生成完整的对比分析报告

		Args:
			results: 按总分降序排列的评分结果

		Returns:
			ComparisonReport：含概况、逐家分析、建议等
		"""
		if not results:
			return ComparisonReport()

		report = ComparisonReport(
			results=results,
			winner=results[0],
		)

		# 生成总体摘要
		report.summary = self._generateSummary(results)

		# 逐家分析
		for r in results:
			report.analysisBySupplier[r.name] = self._analyzeOne(r, results)

		# 整体建议
		report.recommendations = self._generateRecommendations(results)

		return report

	def _generateSummary(self, results: List[SupplierResult]) -> str:
		"""生成总体摘要"""
		if len(results) == 1:
			r = results[0]
			return (
				f'仅有1家供应商「{r.name}」参评，综合得分{r.totalScore}分。'
				f'无法进行横向对比。'
			)

		winner = results[0]
		second = results[1] if len(results) > 1 else None
		last = results[-1]

		lines = [f'共{len(results)}家供应商参评。']

		# 第一名情况
		lines.append(f'[第1名] 「{winner.name}」综合得分{winner.totalScore}分。')

		if second:
			gap = round(winner.totalScore - second.totalScore, 2)
			if gap >= 5:
				lines.append(f'领先第二名「{second.name}」{gap}分，优势明显。')
			elif gap >= 2:
				lines.append(f'领先第二名「{second.name}」{gap}分，有一定优势。')
			else:
				lines.append(f'与第二名「{second.name}」仅差{gap}分，竞争激烈。')

		# 分数分布
		allScores = [r.totalScore for r in results if r.valid]
		if allScores:
			avgScore = round(sum(allScores) / len(allScores), 2)
			maxScore = max(allScores)
			minScore = min(allScores)
			lines.append(f'平均分{avgScore}分，最高{maxScore}分，最低{minScore}分。')

		return '\n'.join(lines)

	def _analyzeOne(self, result: SupplierResult, allResults: List[SupplierResult]) -> str:
		"""逐家分析单个供应商"""
		factors = self.registry.factors
		lines = [f'>> {result.name}（排名第{result.rank}，总分{result.totalScore}分）']

		# 各分项得分
		detailParts = []
		detailParts.append(f'商务：{result.commercialScore}/{factors[1].maxScore}分')
		detailParts.append(f'技术：{result.technicalScore}/{factors[2].maxScore + factors[3].maxScore}分')
		detailParts.append(f'服务：{result.serviceScore}/{factors[4].maxScore + factors[5].maxScore + factors[6].maxScore}分')
		if result.deduction < 0:
			detailParts.append(f'扣分：{result.deduction}分')
		if result.valid:
			detailParts.append(f'价格：{result.priceScore}/{factors[8].maxScore}分')
		else:
			detailParts.append(f'价格：无效（{result.invalidReason}）')
		lines.append('　'.join(detailParts))

		# 优势
		if result.strengths:
			lines.append(f'[优势]：{"；".join(result.strengths)}')
		else:
			lines.append('[优势]：无明显突出项')

		# 短板
		if result.weaknesses:
			lines.append(f'[短板]：{"；".join(result.weaknesses)}')
		else:
			lines.append('[短板]：无明显短板')

		# 改进建议
		improvements = self._suggestImprovements(result, allResults)
		if improvements:
			lines.append(f'[建议]：{"; ".join(improvements)}')

		return '\n'.join(lines)

	def _suggestImprovements(self, result: SupplierResult,
							 allResults: List[SupplierResult]) -> List[str]:
		"""生成针对性改进建议"""
		suggestions = []

		# 如果排名不是第一，分析差距
		if result.rank > 1 and allResults:
			winner = allResults[0]
			gap = round(winner.totalScore - result.totalScore, 2)

			# 分析哪项差距最大
			gaps = {}
			if winner.commercialScore > result.commercialScore:
				gaps['商务'] = round(winner.commercialScore - result.commercialScore, 1)
			if winner.technicalScore > result.technicalScore:
				gaps['技术'] = round(winner.technicalScore - result.technicalScore, 1)
			if winner.serviceScore > result.serviceScore:
				gaps['服务'] = round(winner.serviceScore - result.serviceScore, 1)
			if winner.priceScore > result.priceScore:
				gaps['价格'] = round(winner.priceScore - result.priceScore, 1)

			if gaps:
				biggestGap = max(gaps, key=gaps.get)
				suggestions.append(
					f'与第一名差距{gap}分，主要在「{biggestGap}」落后{gaps[biggestGap]}分，建议重点提升此项'
				)

		# 针对具体短板
		for w in result.weaknesses:
			if '业绩' in w:
				suggestions.append('可补充更多类似视频系统项目业绩合同')
			if '团队' in w:
				suggestions.append('可增加具备2年以上经验的团队成员')
			if '故障' in w:
				suggestions.append('建议优化应急响应流程，压缩故障处理时限')
			if '服务方案' in w or '方案' in w:
				suggestions.append('建议完善服务方案文档，增强针对性和可行性')
			if '扣分' in w:
				suggestions.append('关注供应商管理规定，避免列入限制型名单')
			if '价格' in w:
				suggestions.append('建议调整报价策略，更贴近基准价')

		return suggestions[:3]  # 最多3条建议

	def _generateRecommendations(self, results: List[SupplierResult]) -> List[str]:
		"""生成整体建议"""
		if len(results) < 2:
			return ['仅1家供应商，建议引入更多竞争者以增强议价能力。']

		recs = []
		winner = results[0]

		# 推荐
		recs.append(f'>> 综合推荐「{winner.name}」，综合得分最高（{winner.totalScore}分）')

		# 检查是否所有供应商都有同样的问题
		allWeakKeywords = []
		for r in results:
			for w in r.weaknesses:
				allWeakKeywords.append(w)

		if allWeakKeywords:
			# 统计最常见的短板
			from collections import Counter
			keywordCount = Counter()
			for w in allWeakKeywords:
				if '业绩' in w:
					keywordCount['商务业绩'] += 1
				if '团队' in w:
					keywordCount['技术团队'] += 1
				if '价格' in w:
					keywordCount['价格'] += 1
				if '方案' in w:
					keywordCount['服务方案'] += 1
				if '扣分' in w:
					keywordCount['扣分项'] += 1

			# 超过半数供应商共有的问题
			threshold = len(results) // 2 + 1
			for key, count in keywordCount.most_common(3):
				if count >= threshold:
					recs.append(f'[*] 过半供应商在「{key}」方面存在短板，建议作为重点评审考量')

		return recs
