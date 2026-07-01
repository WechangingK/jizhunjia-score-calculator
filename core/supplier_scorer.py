# -*- coding: utf-8 -*-
"""供应商综合评分计算器

对单个供应商的8项评审因素进行综合评分，并支持批量计算。
价格部分（序号8）复用 PriceCalculator。
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from core.calculator import PriceCalculator
from core.evaluation_factors import FactorRegistry
from core.rule_engine import RuleManager, ScoringRule


@dataclass
class SupplierInput:
	"""供应商评审数据输入

	用户填写的各项原始数据。
	"""
	name: str = ''                      # 供应商名称
	contractCount: int = 0              # 序号1: 类似项目业绩数量
	teamCount: int = 0                  # 序号2: 合格团队人数
	faultHours: float = 8.0             # 序号3: 承诺故障处理小时数
	servicePlanScore: float = 0.0       # 序号4: 整体服务方案得分 (0-3)
	qualityPlanScore: float = 0.0       # 序号5: 质量控制方案得分 (0-3)
	emergencyPlanScore: float = 0.0     # 序号6: 应急响应方案得分 (0-3)
	isRestricted: bool = False          # 序号7: 是否限制型供应商
	price: float = 0.0                  # 序号8: 不含税报价


@dataclass
class SupplierResult:
	"""供应商综合评分结果"""
	name: str = ''                                  # 供应商名称
	inputData: SupplierInput = field(default_factory=SupplierInput)  # 原始输入
	factorScores: Dict[int, float] = field(default_factory=dict)    # {序号: 得分}
	commercialScore: float = 0.0                    # 商务得分 (序号1)
	technicalScore: float = 0.0                     # 技术得分 (序号2+3)
	serviceScore: float = 0.0                       # 服务得分 (序号4+5+6)
	priceScore: float = 0.0                         # 价格得分 (序号8)
	deduction: float = 0.0                          # 扣分 (序号7)
	totalScore: float = 0.0                         # 总分
	rank: int = 0                                   # 排名
	strengths: List[str] = field(default_factory=list)   # 优势项
	weaknesses: List[str] = field(default_factory=list)  # 短板
	valid: bool = True                              # 价格是否有效
	invalidReason: str = ''                         # 无效原因


class SupplierScorer:
	"""供应商综合评分器

	用法:
		registry = FactorRegistry()
		ruleManager = RuleManager.getInstance()
		scorer = SupplierScorer(ruleManager, registry)

		inputs = [SupplierInput(name='公司A', contractCount=4, ...), ...]
		results = scorer.scoreAll(inputs)
	"""

	def __init__(self, ruleManager: RuleManager, factorRegistry: FactorRegistry):
		self.ruleManager = ruleManager
		self.registry = factorRegistry

	def _scoreNonPriceFactors(self, supplier: SupplierInput) -> Dict[int, float]:
		"""计算非价格因素得分（序号1-7）

		Returns:
			{序号: 得分} 字典
		"""
		scores = {}

		# 序号1: 类似项目业绩
		scores[1] = self.registry.scoreFactor(1, supplier.contractCount)

		# 序号2: 团队人员
		scores[2] = self.registry.scoreFactor(2, supplier.teamCount)

		# 序号3: 故障处理时限
		scores[3] = self.registry.scoreFactor(3, supplier.faultHours)

		# 序号4: 整体服务方案
		scores[4] = self.registry.scoreFactor(4, supplier.servicePlanScore)

		# 序号5: 质量控制方案
		scores[5] = self.registry.scoreFactor(5, supplier.qualityPlanScore)

		# 序号6: 应急响应方案
		scores[6] = self.registry.scoreFactor(6, supplier.emergencyPlanScore)

		# 序号7: 扣分项
		scores[7] = self.registry.scoreFactor(7, supplier.isRestricted)

		return scores

	def _analyzeSupplier(self, result: SupplierResult):
		"""分析供应商的优劣势

		根据各分项得分率判断强项和短板。
		"""
		factors = self.registry.factors
		strengths = []
		weaknesses = []

		# 非价格因素分析
		for fid in range(1, 7):
			factor = factors[fid]
			score = result.factorScores.get(fid, 0)
			if factor.maxScore > 0:
				rate = score / factor.maxScore
				if rate >= 0.9:
					strengths.append(f'{factor.name}得分率{rate:.0%}（{score}/{factor.maxScore}分）')
				elif rate <= 0.5:
					weaknesses.append(f'{factor.name}仅得{score}/{factor.maxScore}分（{rate:.0%}），建议加强')

		# 扣分项分析
		deduction = result.factorScores.get(7, 0)
		if deduction < 0:
			weaknesses.append(f'存在扣分项：限制型供应商扣减{abs(deduction)}分')

		# 价格分析
		factor8 = factors[8]
		if factor8.maxScore > 0 and result.valid:
			priceRate = result.priceScore / factor8.maxScore
			if priceRate >= 0.95:
				strengths.append(f'价格得分优秀（{result.priceScore}/{factor8.maxScore}分）')
			elif priceRate <= 0.7:
				weaknesses.append(f'价格得分较低（{result.priceScore}/{factor8.maxScore}分），报价偏离基准价较大')

		result.strengths = strengths
		result.weaknesses = weaknesses

	def scoreAll(self, suppliers: List[SupplierInput]) -> List[SupplierResult]:
		"""批量计算所有供应商的综合得分

		流程:
		1. 提取所有报价，使用 PriceCalculator 计算基准价和价格得分
		2. 对每个供应商计算非价格因素得分
		3. 汇总总分并排名
		4. 分析优劣势

		Args:
			suppliers: 供应商输入数据列表

		Returns:
			按总分降序排列的评分结果列表
		"""
		if not suppliers:
			return []

		rule = self.ruleManager.getActiveRule()
		priceCalc = PriceCalculator(rule)

		# 价格在综合评审中满分为75（文档定义）
		PRICE_MAX = 75.0
		ruleFullScore = rule.fullScore  # 规则预设的满分（如80）

		# 步骤1: 计算基准价和价格得分
		priceDict = {s.name: s.price for s in suppliers if s.price >= 0}
		calcResult = priceCalc.calculateAll(priceDict)

		# 构建名称→价格结果映射
		priceResultMap = {}
		for r in calcResult.results:
			priceResultMap[r.name] = r

		# 步骤2: 对每个供应商综合计算
		results = []
		for supplier in suppliers:
			result = SupplierResult(name=supplier.name, inputData=supplier)

			# 非价格因素得分
			factorScores = self._scoreNonPriceFactors(supplier)
			result.factorScores = factorScores

			# 价格得分（从规则满分缩放到75分）
			priceResult = priceResultMap.get(supplier.name)
			if priceResult and priceResult.valid and ruleFullScore > 0:
				result.priceScore = round(priceResult.score * (PRICE_MAX / ruleFullScore), 2)
				result.valid = True
			else:
				result.priceScore = 0.0
				result.valid = False
				if priceResult:
					result.invalidReason = priceResult.invalidReason

			result.factorScores[8] = result.priceScore

			# 分类汇总
			result.commercialScore = factorScores.get(1, 0)            # 商务
			result.technicalScore = factorScores.get(2, 0) + factorScores.get(3, 0)  # 技术
			result.serviceScore = (factorScores.get(4, 0) +
								   factorScores.get(5, 0) +
								   factorScores.get(6, 0))             # 服务
			result.deduction = factorScores.get(7, 0)                  # 扣分

			# 总分 = 商务 + 技术 + 服务 + 价格 + 扣分(负值)
			result.totalScore = round(
				result.commercialScore + result.technicalScore +
				result.serviceScore + result.priceScore + result.deduction,
				2
			)
			# 总分不低于0
			if result.totalScore < 0:
				result.totalScore = 0.0

			# 分析优劣势
			self._analyzeSupplier(result)

			results.append(result)

		# 步骤3: 按总分降序排序
		results.sort(key=lambda r: r.totalScore, reverse=True)

		# 步骤4: 排名（同分并列）
		rank = 1
		for i, r in enumerate(results):
			if i > 0 and r.totalScore < results[i - 1].totalScore:
				rank = i + 1
			r.rank = rank

		return results
