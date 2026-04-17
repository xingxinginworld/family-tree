# -*- coding: utf-8 -*-
"""家谱制作工具 - 程序入口"""
import sys
import os

# 自动修复 sys.path：确保从任何目录执行都能找到 family_tree 包
# 例如：python family_tree/main.py  或  python -m family_tree.main
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import tkinter as tk
from family_tree.db import init_db
from family_tree.app import FamilyTreeApp


if __name__ == "__main__":
    init_db()
    root = tk.Tk()
    app = FamilyTreeApp(root)
    root.mainloop()
