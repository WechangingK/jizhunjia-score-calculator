# -*- mode: python ; coding: utf-8 -*-
# PyInstaller 打包配置 - 基准价得分计算器

import os, sys
block_cipher = None

from PyInstaller.utils.hooks import collect_submodules

hidden_imports = list(set(
	collect_submodules('pandas') +
	collect_submodules('openpyxl') +
	collect_submodules('xml') +
	['secrets', 'pyexpat', '_elementtree', 'xml.parsers.expat']
))

# 收集 Python/DLLs 下的 C 扩展
_binaries = []

_dll_dir = os.path.join(sys.prefix, 'DLLs')
if os.path.isdir(_dll_dir):
	for _f in os.listdir(_dll_dir):
		_fp = os.path.join(_dll_dir, _f)
		if os.path.isfile(_fp) and _f.endswith('.pyd'):
			_binaries.append((_fp, '.'))

a = Analysis(
	['main.py'],
	pathex=[SPECPATH],
	binaries=_binaries,
	datas=[],
	hiddenimports=hidden_imports,
	hookspath=[],
	hooksconfig={},
	runtime_hooks=[],
	excludes=[
		'PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets',
		'PySide6.QtWebChannel', 'PySide6.QtQml', 'PySide6.QtQuick',
		'PySide6.QtMultimedia', 'PySide6.QtPdf', 'PySide6.QtPdfWidgets',
		'PySide6.QtQuickWidgets', 'PySide6.QtTextToSpeech',
		'PySide6.Qt3DCore', 'PySide6.Qt3DRender', 'PySide6.Qt3DInput',
		'PySide6.QtDesigner', 'PySide6.QtHelp', 'PySide6.QtUiTools',
		'PySide6.QtAxContainer',
		'matplotlib', 'scipy', 'PIL', 'tkinter',
		'jupyter', 'ipykernel', 'IPython', 'nbformat',
		'distutils', 'setuptools', 'pip',
	],
	win_no_prefer_redirects=False,
	win_private_assemblies=False,
	cipher=block_cipher,
	noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
	pyz,
	a.scripts,
	a.binaries,
	a.datas,
	[],
	name='JizhunjiaScoreCalculator',
	debug=False,
	bootloader_ignore_signals=False,
	strip=True,
	upx=True,
	runtime_tmpdir=None,
	console=False,
)
