#!/usr/bin/env python3
"""
Import every module under src/ and report the ones that fail.

The unit tests only reach a fraction of the tree, so a typo in a view or a
dialog that is opened rarely would otherwise surface as a crash in front of the
user. Run with QT_QPA_PLATFORM=offscreen on a headless machine.
"""

from __future__ import annotations

import importlib
import os
import pkgutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'src'


def module_names() -> list[str]:
    return sorted(info.name for info in pkgutil.walk_packages([str(SRC)]))


def main() -> int:
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(SRC))
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

    # A QApplication has to exist before widget modules define widgets that
    # touch the style at import time.
    from PySide6.QtWidgets import QApplication
    QApplication(sys.argv[:1])

    failures: list[tuple[str, BaseException]] = []
    names = module_names()

    for name in names:
        try:
            importlib.import_module(name)
        except BaseException as exc:  # noqa: BLE001 - report everything
            failures.append((name, exc))

    for name, exc in failures:
        print(f'FAIL {name}: {type(exc).__name__}: {exc}', file=sys.stderr)

    print(f'{len(names) - len(failures)}/{len(names)} modules imported')
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
