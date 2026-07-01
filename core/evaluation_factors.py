# -*- coding: utf-8 -*-
"""评审因素定义引擎

根据详细评审表-2025定义8个评审因素的数据结构和计算逻辑。
"""

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional


@dataclass
class FactorDefinition:
	"""单个评审因素定义"""
	id: int                    # 序号 1-8
	name: str                  # 因素名称
	category: str              # 类别：商务/技术/服务/扣分/价格
	maxScore: float            # 满分
	inputType: str             # 输入类型: 'count' | 'hours' | 'tier' | 'boolean' | 'price'
	description: str           # 评分标准说明
	detailRule: str = ''       # 详细评分规则
	inputLabel: str = ''       # 输入列标签


class FactorRegistry:
	"""评审因素注册表

	管理8个评审因素，提供统一的评分计算接口。
	"""

	def __init__(self):
		self._factors: Dict[int, FactorDefinition] = {}
		self._scorers: Dict[int, Callable] = {}
		self._registerAll()

	def _registerAll(self):
		"""注册全部8个评审因素"""
		# 序号1: 类似项目业绩 (商务 8分)
		self._factors[1] = FactorDefinition(
			id=1, name='类似项目业绩', category='商务',
			maxScore=8, inputType='count',
			description='自2023年1月1日起类似视频系统项目业绩',
			detailRule='每多提供1份有效合同得2分，最多8分',
			inputLabel='有效合同数',
		)
		self._scorers[1] = lambda count: min(int(count or 0) * 2, 8)

		# 序号2: 团队人员 (技术 6分)
		self._factors[2] = FactorDefinition(
			id=2, name='团队人员', category='技术',
			maxScore=6, inputType='count',
			description='具备2年以上工作经验的团队人员',
			detailRule='每人得2分，最多6分（需提供劳动合同+社保）',
			inputLabel='合格人数',
		)
		self._scorers[2] = lambda count: min(int(count or 0) * 2, 6)

		# 序号3: 故障处理时限 (技术 2分)
		self._factors[3] = FactorDefinition(
			id=3, name='故障处理时限', category='技术',
			maxScore=2, inputType='hours',
			description='重大系统故障及安全事件应急处理时间',
			detailRule='比8小时基准每提前1小时得1分，最多2分（须提供承诺函）',
			inputLabel='承诺小时数',
		)
		self._scorers[3] = lambda hours: min(max(8 - float(hours or 8), 0) * 1, 2)

		# 序号4: 整体服务方案 (服务 3分)
		self._factors[4] = FactorDefinition(
			id=4, name='整体服务方案', category='服务',
			maxScore=3, inputType='tier',
			description='包含项目背景理解、执行方案、实施计划等',
			detailRule='2-3分：方案严密、内容齐全、有针对性\n1-2分：方案较为严密、合理性一般\n0-1分：方案与项目不匹配、可行性差',
			inputLabel='方案得分(0-3)',
		)
		self._scorers[4] = lambda score: min(max(float(score or 0), 0), 3)

		# 序号5: 质量控制方案 (服务 3分)
		self._factors[5] = FactorDefinition(
			id=5, name='质量控制方案', category='服务',
			maxScore=3, inputType='tier',
			description='工作流程、目标、原则、质量标准、进度计划等',
			detailRule='2-3分：内容齐全、有针对性、合理可行\n1-2分：内容较齐全、合理性一般\n0-1分：内容合理性差、可行性差',
			inputLabel='方案得分(0-3)',
		)
		self._scorers[5] = lambda score: min(max(float(score or 0), 0), 3)

		# 序号6: 应急响应方案 (服务 3分)
		self._factors[6] = FactorDefinition(
			id=6, name='应急响应方案', category='服务',
			maxScore=3, inputType='tier',
			description='应急响应方案、服务体系、应急预案等',
			detailRule='2-3分：全面具体、服务体系完备、可行性强\n1-2分：较为全面、有一定可行性\n0-1分：方案一般、可行性一般',
			inputLabel='方案得分(0-3)',
		)
		self._scorers[6] = lambda score: min(max(float(score or 0), 0), 3)

		# 序号7: 扣分项 (扣分 -3/0)
		self._factors[7] = FactorDefinition(
			id=7, name='扣分项（限制型供应商）', category='扣分',
			maxScore=0, inputType='boolean',
			description='因业务不可替代暂不列入黑名单的限制型供应商',
			detailRule='限制型供应商综合评分扣减3分',
			inputLabel='是否限制型',
		)
		self._scorers[7] = lambda isRestricted: -3 if isRestricted else 0

		# 序号8: 价格 - 由 PriceCalculator 单独处理，这里仅作登记
		self._factors[8] = FactorDefinition(
			id=8, name='价格（基准价法）', category='价格',
			maxScore=75, inputType='price',
			description='采用基准价最优法计算价格得分',
			detailRule='B=A得满分75分\nB>A每高1%扣0.6分\nB<A每低1%扣0.3分\n负分按0分计',
			inputLabel='不含税总价（元）',
		)

	@property
	def factors(self) -> Dict[int, FactorDefinition]:
		"""获取所有因素"""
		return self._factors

	def getFactor(self, factorId: int) -> Optional[FactorDefinition]:
		"""获取单个因素定义"""
		return self._factors.get(factorId)

	def getInputFactors(self) -> List[FactorDefinition]:
		"""获取需要用户输入的因素列表（序号1-7，8号价格单独处理）"""
		return [self._factors[i] for i in range(1, 9)]

	def getNonPriceFactors(self) -> List[FactorDefinition]:
		"""获取非价格因素列表（序号1-7）"""
		return [self._factors[i] for i in range(1, 8)]

	def scoreFactor(self, factorId: int, value) -> float:
		"""计算单个因素得分

		Args:
			factorId: 因素序号 1-7
			value: 输入值（类型取决于因素）

		Returns:
			该因素得分
		"""
		scorer = self._scorers.get(factorId)
		if scorer is None:
			return 0.0
		result = scorer(value)
		return round(result, 2)

	def factorSummary(self) -> str:
		"""生成评审因素概览文字"""
		lines = []
		totalMax = 0
		for fid in range(1, 9):
			f = self._factors[fid]
			lines.append(f'{f.id}. [{f.category}] {f.name}: {f.maxScore}分')
			totalMax += f.maxScore
		lines.append(f'---\n总分: {totalMax}分')
		return '\n'.join(lines)
