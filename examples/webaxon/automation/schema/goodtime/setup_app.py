"""
py2app setup script for GoodTime Automation
Creates a standalone macOS .app bundle
"""

from setuptools import setup

APP = ['run_goodtime_template_selection_graph_with_monitor.py']
DATA_FILES = [
    'create_goodtime_template_selection_graph_with_monitor.py',
]

OPTIONS = {
    'argv_emulation': False,
    'packages': [
        'webaxon',
        'agent_foundation',
        'rich_python_utils',
    ],
    'excludes': [
        'torch',
        'tensorflow',
        'sklearn',
        'matplotlib',
        'scipy',
        'pytest',
        'unittest',
        'sphinx',
        'docutils',
        'tkinter',
        'test',
        'IPython',
        'notebook',
        'jupyter',
    ],
    'site_packages': True,
    'resources': [],
    'plist': {
        'CFBundleName': 'GoodTime Automation',
        'CFBundleDisplayName': 'GoodTime Template Selection',
        'CFBundleIdentifier': 'com.yourcompany.goodtime',
        'CFBundleVersion': '0.1.0',
        'CFBundleShortVersionString': '0.1.0',
        'NSHumanReadableCopyright': '© 2026 Your Company',
        'LSMinimumSystemVersion': '10.13.0',
    },
    'iconfile': None,
}

setup(
    name='GoodTime Automation',
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
