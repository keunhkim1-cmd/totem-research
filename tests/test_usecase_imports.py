from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_public_usecases_import_without_financial_model():
    code = """
import importlib.abc
import sys

class BlockFinancialModel(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'lib.financial_model':
            raise RuntimeError('lib.financial_model should be lazy-loaded')
        return None

sys.meta_path.insert(0, BlockFinancialModel())
import lib.usecases
print('ok')
"""
    result = subprocess.run(
        [sys.executable, '-c', code],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout.strip() == 'ok'
