# -*- coding: utf-8 -*-
"""评分规则引擎

管理评分规则的创建、编辑、删除、持久化。
内置4套常用预设规则。
"""

import json
import os
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class TrimTier:
	"""一个去极值区间

	minCount=0 作为兜底区间，必须存在。
	匹配时按 minCount 降序，找到第一个满足 count >= minCount 的区间。
	"""
	minCount: int          # 最少应答人数
	removeHigh: int        # 去掉几个最高值
	removeLow: int         # 去掉几个最低值


@dataclass
class ScoringRule:
	"""评分规则"""
	id: str = ''                              # 唯一标识
	name: str = '新规则'                        # 规则名称
	description: str = ''                      # 规则说明
	fullScore: float = 80.0                    # 满分
	maxPrice: float = 0.0                      # 最高限价（0=不限价）
	highPenalty: float = 0.6                   # 高于基准价每1%扣分
	lowPenalty: float = 0.3                    # 低于基准价每1%扣分
	trimTiers: List[TrimTier] = field(default_factory=lambda: [
		TrimTier(10, 2, 2),
		TrimTier(5, 1, 1),
		TrimTier(0, 0, 0),
	])
	decimals: int = 2                          # 小数保留位
	isPreset: bool = False                     # 是否内置预设

	def toDict(self) -> dict:
		"""序列化为字典"""
		return {
			'id': self.id,
			'name': self.name,
			'description': self.description,
			'fullScore': self.fullScore,
			'maxPrice': self.maxPrice,
			'highPenalty': self.highPenalty,
			'lowPenalty': self.lowPenalty,
			'trimTiers': [
				{'minCount': t.minCount, 'removeHigh': t.removeHigh, 'removeLow': t.removeLow}
				for t in self.trimTiers
			],
			'decimals': self.decimals,
		}

	@classmethod
	def fromDict(cls, data: dict, isPreset: bool = False) -> 'ScoringRule':
		"""从字典反序列化"""
		tiers = [
			TrimTier(t.get('minCount', 0), t.get('removeHigh', 0), t.get('removeLow', 0))
			for t in data.get('trimTiers', [])
		]
		if not tiers:
			tiers = [TrimTier(0, 0, 0)]
		# 确保按minCount降序
		tiers.sort(key=lambda t: t.minCount, reverse=True)

		return cls(
			id=data.get('id', ''),
			name=data.get('name', '新规则'),
			description=data.get('description', ''),
			fullScore=data.get('fullScore', 80.0),
			maxPrice=data.get('maxPrice', 0.0),
			highPenalty=data.get('highPenalty', 0.6),
			lowPenalty=data.get('lowPenalty', 0.3),
			trimTiers=tiers,
			decimals=data.get('decimals', 2),
			isPreset=isPreset,
		)

	def summaryText(self) -> str:
		"""生成规则摘要文本，用于界面上快速展示"""
		parts = [f'满分{self.fullScore}分']
		if self.maxPrice > 0:
			parts.append(f'最高限价{self.maxPrice:,.2f}元')
		else:
			parts.append('不限价')
		parts.append(f'高扣{self.highPenalty}/低扣{self.lowPenalty}')
		# 去极值摘要
		trimParts = []
		for t in self.trimTiers:
			if t.minCount > 0:
				trimParts.append(f'≥{t.minCount}家去{t.removeHigh}高{t.removeLow}低')
			else:
				if t.removeHigh == 0 and t.removeLow == 0:
					trimParts.append('其余不去')
				else:
					trimParts.append(f'其余去{t.removeHigh}高{t.removeLow}低')
		parts.append('｜' + '，'.join(trimParts))
		return '，'.join(parts)

	def getMatchedTier(self, count: int) -> TrimTier:
		"""根据应答人数量匹配去极值规则"""
		for t in self.trimTiers:
			if count >= t.minCount:
				return t
		return self.trimTiers[-1] if self.trimTiers else TrimTier(0, 0, 0)


# 内置预设规则
def _build_presets() -> Dict[str, ScoringRule]:
	"""构建内置预设规则"""
	standardTiers = [
		TrimTier(10, 2, 2),
		TrimTier(5, 1, 1),
		TrimTier(0, 0, 0),
	]
	return {
		'preset_text': ScoringRule(
			id='preset_text', name='标准文字描述法',
			description='文字描述方案：高1%扣0.6，低1%扣0.3，满分80',
			fullScore=80, maxPrice=0, highPenalty=0.6, lowPenalty=0.3,
			trimTiers=standardTiers, isPreset=True,
		),
		'preset_formula': ScoringRule(
			id='preset_formula', name='标准公式法',
			description='公式方案：高1%扣0.4，低1%扣0.2，满分80',
			fullScore=80, maxPrice=0, highPenalty=0.4, lowPenalty=0.2,
			trimTiers=standardTiers, isPreset=True,
		),
		'preset_composite': ScoringRule(
			id='preset_composite', name='综合评估法',
			description='满分100，高低均扣0.5，适合综合评分',
			fullScore=100, maxPrice=0, highPenalty=0.5, lowPenalty=0.5,
			trimTiers=standardTiers, isPreset=True,
		),
		'preset_lowest': ScoringRule(
			id='preset_lowest', name='最低价优先法',
			description='高1%扣1.0分（惩罚重），低1%扣0.5分，鼓励低价',
			fullScore=80, maxPrice=0, highPenalty=1.0, lowPenalty=0.5,
			trimTiers=standardTiers, isPreset=True,
		),
	}


class RuleManager:
	"""规则管理器（单例模式）"""

	_instance: Optional['RuleManager'] = None
	_dataDir: str = ''

	@classmethod
	def getInstance(cls) -> 'RuleManager':
		"""获取单例"""
		if cls._instance is None:
			cls._instance = cls()
		return cls._instance

	def __init__(self):
		if RuleManager._instance is not None:
			return  # 单例已存在
		RuleManager._instance = self

		self.rules: Dict[str, ScoringRule] = {}
		self.activeRuleId: str = 'preset_text'  # 默认选中

		# 确定data目录
		self._resolveDataDir()
		self._loadPresets()
		self._loadUserRules()

	def _resolveDataDir(self):
		"""确定数据存储目录"""
		# 尝试查找项目 data 目录
		candidates = [
			os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data'),
		]
		for d in candidates:
			if os.path.isdir(d):
				self._dataDir = d
				return
		# 兜底：在当前目录创建
		self._dataDir = os.path.join(os.getcwd(), 'data')
		os.makedirs(self._dataDir, exist_ok=True)

	@property
	def rulesPath(self) -> str:
		return os.path.join(self._dataDir, 'rules.json')

	def _loadPresets(self):
		"""加载内置预设规则"""
		for preset in _build_presets().values():
			self.rules[preset.id] = preset

	def _loadUserRules(self):
		"""从文件加载用户自定义规则"""
		if not os.path.exists(self.rulesPath):
			return
		try:
			with open(self.rulesPath, 'r', encoding='utf-8') as f:
				data = json.load(f)
			for item in data:
				rule = ScoringRule.fromDict(item)
				if rule.id and rule.id not in self.rules:
					self.rules[rule.id] = rule
		except (json.JSONDecodeError, KeyError) as e:
			print(f'[RuleManager] 加载用户规则失败: {e}')

	def save(self):
		"""持久化用户自定义规则"""
		userRules = [r.toDict() for r in self.rules.values() if not r.isPreset]
		os.makedirs(os.path.dirname(self.rulesPath), exist_ok=True)
		with open(self.rulesPath, 'w', encoding='utf-8') as f:
			json.dump(userRules, f, ensure_ascii=False, indent=2)

	def listRules(self) -> List[ScoringRule]:
		"""列出所有规则（预设在前，用户规则在后）"""
		presets = [r for r in self.rules.values() if r.isPreset]
		users = [r for r in self.rules.values() if not r.isPreset]
		return presets + users

	def getRule(self, ruleId: str) -> Optional[ScoringRule]:
		"""获取指定规则"""
		return self.rules.get(ruleId)

	def getActiveRule(self) -> ScoringRule:
		"""获取当前激活的规则"""
		return self.rules.get(self.activeRuleId, list(self.rules.values())[0])

	def setActiveRule(self, ruleId: str):
		"""设置当前激活规则"""
		if ruleId in self.rules:
			self.activeRuleId = ruleId

	def addRule(self, rule: ScoringRule):
		"""新增规则，自动生成ID"""
		if not rule.id:
			rule.id = f'rule_{uuid.uuid4().hex[:8]}'
		rule.isPreset = False
		self.rules[rule.id] = rule
		self.save()

	def updateRule(self, rule: ScoringRule):
		"""更新规则"""
		if rule.id in self.rules:
			self.rules[rule.id] = rule
			self.save()

	def deleteRule(self, ruleId: str) -> bool:
		"""删除规则（预设不可删）"""
		rule = self.rules.get(ruleId)
		if rule is None:
			return False
		if rule.isPreset:
			return False
		del self.rules[ruleId]
		# 如果当前激活的是被删的规则，切回第一个预设
		if self.activeRuleId == ruleId:
			self.activeRuleId = 'preset_text'
		self.save()
		return True

	def duplicateRule(self, ruleId: str) -> Optional[ScoringRule]:
		"""复制规则"""
		source = self.rules.get(ruleId)
		if source is None:
			return None
		newRule = ScoringRule(
			name=f'{source.name}（副本）',
			description=source.description,
			fullScore=source.fullScore,
			maxPrice=source.maxPrice,
			highPenalty=source.highPenalty,
			lowPenalty=source.lowPenalty,
			trimTiers=[TrimTier(t.minCount, t.removeHigh, t.removeLow) for t in source.trimTiers],
			decimals=source.decimals,
			isPreset=False,
		)
		self.addRule(newRule)
		return newRule
