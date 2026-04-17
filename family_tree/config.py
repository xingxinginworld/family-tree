# -*- coding: utf-8 -*-
"""配置模块"""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "..", "family_tree.db")
PHOTO_DIR = os.path.join(BASE_DIR, "..", "photos")
