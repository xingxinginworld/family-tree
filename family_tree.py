# ⚠️ 已废弃！请使用 `family_tree/main.py` 启动程序
# 此文件已拆分为多文件模块，保留作为参考
# ─────────────────────────────────────────────
# -*- coding: utf-8 -*-
"""
家谱制作工具 v1.9.2（废弃）
支持成员管理、家谱树可视化、照片墙、HTML 导出、CSV 导入导出
运行环境：Python 3.8+，依赖 Pillow
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sqlite3
import os
import json
import shutil
import base64
import csv
from datetime import datetime
from PIL import Image, ImageTk

# ========== 配置 ==========
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "family_tree.db")
PHOTO_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "photos")


# ========== 数据库 ==========
def init_db():
    os.makedirs(PHOTO_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # 建表
    c.execute("""
        CREATE TABLE IF NOT EXISTS members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            gender TEXT,
            birth_date TEXT,
            death_date TEXT,
            father_id INTEGER,
            mother_id INTEGER,
            spouse1_id INTEGER,
            spouse2_id INTEGER,
            bio TEXT,
            photo_path TEXT,
            extra_photos TEXT,
            generation INTEGER DEFAULT 0,
            x_pos REAL DEFAULT 0,
            y_pos REAL DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 迁移：旧表补充 spouse1_id / spouse2_id 列
    c.execute("PRAGMA table_info(members)")
    columns = [row[1] for row in c.fetchall()]
    if "spouse1_id" not in columns:
        c.execute("ALTER TABLE members ADD COLUMN spouse1_id INTEGER")
    if "spouse2_id" not in columns:
        c.execute("ALTER TABLE members ADD COLUMN spouse2_id INTEGER")
    # 旧 spouse_id → spouse1_id
    if "spouse_id" in columns and "spouse1_id" in columns:
        c.execute("UPDATE members SET spouse1_id=spouse_id WHERE spouse_id IS NOT NULL AND spouse1_id IS NULL")
        c.execute("DROP INDEX IF EXISTS idx_spouse_id")

    c.execute("""
        CREATE TABLE IF NOT EXISTS photo_wall (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT NOT NULL,
            caption TEXT,
            member_id INTEGER,
            sort_order INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()


def get_conn():
    return sqlite3.connect(DB_PATH)


# ========== 数据模型 ==========
class Member:
    def __init__(self, row):
        self.id = row[0]
        self.name = row[1]
        self.gender = row[2]
        self.birth_date = row[3]
        self.death_date = row[4]
        self.father_id = row[5]
        self.mother_id = row[6]
        self.bio = row[7]
        self.photo_path = row[8]
        self.extra_photos = json.loads(row[9]) if row[9] else []
        self.generation = row[10]
        self.x_pos = row[11]
        self.y_pos = row[12]
        self.spouse_id = row[14]      # 旧字段（废弃但保留）
        self.spouse1_id = row[15]
        self.spouse2_id = row[16] if len(row) > 16 else None


class WallPhoto:
    def __init__(self, row):
        self.id = row[0]
        self.file_path = row[1]
        self.caption = row[2]
        self.member_id = row[3]
        self.sort_order = row[4]


def get_all_members():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""SELECT id, name, gender, birth_date, death_date, father_id, mother_id, bio, photo_path, extra_photos, generation, x_pos, y_pos, created_at, spouse_id, spouse1_id, spouse2_id FROM members ORDER BY generation, id""")
    rows = c.fetchall()
    conn.close()
    return [Member(row) for row in rows]


def get_member_by_id(member_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""SELECT id, name, gender, birth_date, death_date, father_id, mother_id, bio, photo_path, extra_photos, generation, x_pos, y_pos, created_at, spouse_id, spouse1_id, spouse2_id FROM members WHERE id=?""", (member_id,))
    row = c.fetchone()
    conn.close()
    return Member(row) if row else None


def get_all_wall_photos():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM photo_wall ORDER BY sort_order, id")
    rows = c.fetchall()
    conn.close()
    return [WallPhoto(row) for row in rows]


def save_member(data, member_id=None):
    conn = get_conn()
    c = conn.cursor()

    if member_id is None:
        c.execute("""
            INSERT INTO members (name, gender, birth_date, death_date, father_id,
            mother_id, spouse1_id, spouse2_id, bio, photo_path, extra_photos, generation)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data['name'], data.get('gender'), data.get('birth_date'),
            data.get('death_date'), data.get('father_id'), data.get('mother_id'),
            data.get('spouse1_id'), data.get('spouse2_id'),
            data.get('bio'), data.get('photo_path'),
            json.dumps(data.get('extra_photos', [])), data.get('generation', 0)
        ))
    else:
        c.execute("""
            UPDATE members SET name=?, gender=?, birth_date=?, death_date=?,
            father_id=?, mother_id=?, spouse1_id=?, spouse2_id=?, bio=?, photo_path=?,
            extra_photos=?, generation=?
            WHERE id=?
        """, (
            data['name'], data.get('gender'), data.get('birth_date'),
            data.get('death_date'), data.get('father_id'), data.get('mother_id'),
            data.get('spouse1_id'), data.get('spouse2_id'),
            data.get('bio'), data.get('photo_path'),
            json.dumps(data.get('extra_photos', [])), data.get('generation', 0),
            member_id
        ))

    conn.commit()
    member_id_out = c.lastrowid if member_id is None else member_id
    conn.close()

    calc_generations()
    return member_id_out


def delete_member(member_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE members SET father_id=NULL WHERE father_id=?", (member_id,))
    c.execute("UPDATE members SET mother_id=NULL WHERE mother_id=?", (member_id,))
    c.execute("UPDATE members SET spouse1_id=NULL WHERE spouse1_id=?", (member_id,))
    c.execute("UPDATE members SET spouse2_id=NULL WHERE spouse2_id=?", (member_id,))
    c.execute("DELETE FROM members WHERE id=?", (member_id,))
    conn.commit()
    conn.close()
    calc_generations()


def delete_wall_photo(photo_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT file_path FROM photo_wall WHERE id=?", (photo_id,))
    row = c.fetchone()
    if row and row[0] and os.path.exists(row[0]):
        try:
            os.remove(row[0])
        except:
            pass
    c.execute("DELETE FROM photo_wall WHERE id=?", (photo_id,))
    conn.commit()
    conn.close()


def calc_generations():
    conn = get_conn()
    c = conn.cursor()

    c.execute("""
        SELECT id FROM members
        WHERE father_id IS NULL AND mother_id IS NULL
        AND id NOT IN (
            SELECT father_id FROM members WHERE father_id IS NOT NULL
            UNION
            SELECT mother_id FROM members WHERE mother_id IS NOT NULL
        )
    """)
    roots = [r[0] for r in c.fetchall()]

    visited = set()
    queue = []
    for root in roots:
        c.execute("UPDATE members SET generation=0 WHERE id=?", (root,))
        queue.append((root, 0))
        visited.add(root)

    while queue:
        pid, gen = queue.pop(0)
        c.execute(
            "SELECT id FROM members WHERE (father_id=? OR mother_id=?) AND id NOT IN ("
            + ",".join("?" * len(visited)) + ")",
            [pid, pid] + list(visited)
        )
        for row in c.fetchall():
            cid = row[0]
            c.execute("UPDATE members SET generation=? WHERE id=?", (gen + 1, cid))
            queue.append((cid, gen + 1))
            visited.add(cid)

    c.execute("SELECT id, generation FROM members WHERE id NOT IN ("
              + ",".join("?" * len(visited)) + ")", list(visited))
    for row in c.fetchall():
        if row[1] is None or row[1] == 0:
            c.execute("UPDATE members SET generation=0 WHERE id=?", (row[0],))

    conn.commit()
    conn.close()


# ========== 主程序 ==========
class FamilyTreeApp:
    def __init__(self, root):
        self.root = root
        self.root.title("家谱制作工具 v1.9.2")
        self.root.geometry("1100x750")

        self.members = []
        self.member_map = {}

        self.tree_canvas = None
        self.canvas_items = {}
        self.node_width = 120
        self.node_height = 60
        self.level_height = 100
        self.tree_photo_images = {}
        self.wall_photo_images = {}

        self.setup_ui()
        self.load_data()

    def setup_ui(self):
        top_frame = tk.Frame(self.root, height=50, bg="#2c3e50")
        top_frame.pack(fill=tk.X)
        tk.Label(top_frame, text="家谱制作工具", font=("微软雅黑", 16, "bold"),
                 fg="white", bg="#2c3e50").pack(pady=10)

        # 左侧
        left_frame = tk.Frame(self.root, width=260, bg="#ecf0f1")
        left_frame.pack(side=tk.LEFT, fill=tk.Y)
        left_frame.pack_propagate(False)

        tk.Label(left_frame, text="家族成员", font=("微软雅黑", 12, "bold"),
                 bg="#ecf0f1").pack(pady=10)

        search_frame = tk.Frame(left_frame, bg="#ecf0f1")
        search_frame.pack(fill=tk.X, padx=10)
        self.search_var = tk.StringVar()
        self.search_var.trace("w", lambda *a: self.filter_members())
        tk.Entry(search_frame, textvariable=self.search_var,
                font=("微软雅黑", 10)).pack(fill=tk.X)

        list_frame = tk.Frame(left_frame, bg="#ecf0f1")
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.member_listbox = tk.Listbox(list_frame, font=("微软雅黑", 10),
                                          yscrollcommand=scrollbar.set,
                                          selectbackground="#3498db",
                                          selectforeground="white")
        self.member_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.member_listbox.yview)
        self.member_listbox.bind("<<ListboxSelect>>", self.on_member_select)

        btn_frame = tk.Frame(left_frame, bg="#ecf0f1")
        btn_frame.pack(pady=10, padx=10)
        tk.Button(btn_frame, text="添加成员", command=self.add_member_dialog,
                  font=("微软雅黑", 10), width=15, bg="#27ae60", fg="white",
                  activebackground="#219150", cursor="hand2").pack(pady=3)
        tk.Button(btn_frame, text="照片墙", command=self.show_photo_wall,
                  font=("微软雅黑", 10), width=15, bg="#8e44ad", fg="white",
                  activebackground="#732d91", cursor="hand2").pack(pady=3)
        tk.Button(btn_frame, text="导出HTML", command=self.export_html,
                  font=("微软雅黑", 10), width=15, bg="#e67e22", fg="white",
                  activebackground="#d35400", cursor="hand2").pack(pady=3)

        # 导入导出工具栏
        io_frame = tk.Frame(left_frame, bg="#ecf0f1")
        io_frame.pack(pady=(0, 10), padx=10)
        tk.Label(io_frame, text="数据管理", font=("微软雅黑", 9, "bold"),
                 bg="#ecf0f1", fg="#555").pack(pady=(5, 3))
        tk.Button(io_frame, text="下载导入模板", command=self.download_template,
                  font=("微软雅黑", 9), width=15, bg="#16a085", fg="white",
                  cursor="hand2").pack(pady=2)
        tk.Button(io_frame, text="导出成员CSV", command=self.export_members_csv,
                  font=("微软雅黑", 9), width=15, bg="#2980b9", fg="white",
                  cursor="hand2").pack(pady=2)
        tk.Button(io_frame, text="导入成员CSV", command=self.import_members_csv,
                  font=("微软雅黑", 9), width=15, bg="#8e44ad", fg="white",
                  cursor="hand2").pack(pady=2)

        # 右侧
        self.right_frame = tk.Frame(self.root, bg="white")
        self.right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        tk.Label(self.right_frame, text="家谱树（点击节点查看详情）",
                 font=("微软雅黑", 11), bg="white").pack(pady=5)

        toolbar = tk.Frame(self.right_frame, bg="white")
        toolbar.pack(fill=tk.X, padx=10)
        tk.Button(toolbar, text="刷新树", command=self.draw_tree,
                  font=("微软雅黑", 9), bg="#3498db", fg="white",
                  cursor="hand2").pack(side=tk.LEFT, padx=3)
        tk.Button(toolbar, text="放大", command=lambda: self.zoom_tree(1.2),
                  font=("微软雅黑", 9), bg="#95a5a6", fg="white",
                  cursor="hand2").pack(side=tk.LEFT, padx=3)
        tk.Button(toolbar, text="缩小", command=lambda: self.zoom_tree(0.8),
                  font=("微软雅黑", 9), bg="#95a5a6", fg="white",
                  cursor="hand2").pack(side=tk.LEFT, padx=3)

        canvas_frame = tk.Frame(self.right_frame, bg="#f5f5f5")
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.tree_scroll_x = tk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL)
        self.tree_scroll_x.pack(side=tk.BOTTOM, fill=tk.X)
        self.tree_scroll_y = tk.Scrollbar(canvas_frame, orient=tk.VERTICAL)
        self.tree_scroll_y.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree_canvas = tk.Canvas(canvas_frame,
                                       xscrollcommand=self.tree_scroll_x.set,
                                       yscrollcommand=self.tree_scroll_y.set,
                                       bg="#f5f5f5", highlightthickness=0)
        self.tree_canvas.pack(fill=tk.BOTH, expand=True)
        self.tree_scroll_x.config(command=self.tree_canvas.xview)
        self.tree_scroll_y.config(command=self.tree_canvas.yview)

        self.scale = 1.0

    def load_data(self):
        self.members = get_all_members()
        self.member_map = {m.id: m for m in self.members}
        self.update_member_list()
        self.draw_tree()

    def update_member_list(self, filter_text=""):
        self.member_listbox.delete(0, tk.END)
        for m in self.members:
            if filter_text and filter_text.lower() not in m.name.lower():
                continue
            gender_icon = "♂" if m.gender == "男" else "♀" if m.gender == "女" else ""
            self.member_listbox.insert(tk.END, f"{gender_icon} {m.name}")

    def filter_members(self):
        self.update_member_list(self.search_var.get())

    def on_member_select(self, event):
        selection = self.member_listbox.curselection()
        if not selection:
            return
        idx = selection[0]
        filter_text = self.search_var.get()
        filtered = [m for m in self.members
                    if not filter_text or filter_text.lower() in m.name.lower()]
        if idx < len(filtered):
            self.show_member_detail(filtered[idx].id)

    def show_member_detail(self, member_id):
        # 从数据库重新获取，确保显示最新数据（尤其是保存后照片路径已更新的情况）
        member = get_member_by_id(member_id)
        if not member:
            return

        win = tk.Toplevel(self.root)
        win.title(f"成员详情 - {member.name}")
        win.geometry("500x600")
        win.transient(self.root)
        win.grab_set()

        photo_frame = tk.Frame(win)
        photo_frame.pack(pady=10)
        if member.photo_path and os.path.exists(member.photo_path):
            try:
                img = Image.open(member.photo_path)
                img = img.resize((120, 150), Image.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                self.tree_photo_images[f"detail_{member.id}"] = photo
                tk.Label(photo_frame, image=photo).pack()
            except:
                tk.Label(photo_frame, text="[照片无法显示]", font=("微软雅黑", 10),
                         bg="#eee", width=15, height=8).pack()
        else:
            tk.Label(photo_frame, text="[无照片]", font=("微软雅黑", 10),
                     bg="#eee", width=15, height=8).pack()

        info_frame = tk.Frame(win)
        info_frame.pack(fill=tk.X, padx=20, pady=5)

        def info_row(label, value):
            row = tk.Frame(info_frame)
            row.pack(fill=tk.X, pady=2)
            tk.Label(row, text=f"{label}：", font=("微软雅黑", 10, "bold"),
                     width=10, anchor="e").pack(side=tk.LEFT)
            tk.Label(row, text=value, font=("微软雅黑", 10)).pack(side=tk.LEFT)

        info_row("姓名", member.name)
        info_row("性别", member.gender or "未填写")
        info_row("出生日期", member.birth_date or "未填写")
        info_row("逝世日期", member.death_date or "在世")
        info_row("世代", f"第{member.generation + 1}代" if member.generation is not None else "未计算")

        if member.father_id:
            father = self.member_map.get(member.father_id)
            if father:
                info_row("父亲", father.name)
        if member.mother_id:
            mother = self.member_map.get(member.mother_id)
            if mother:
                info_row("母亲", mother.name)

        if member.spouse1_id:
            spouse = self.member_map.get(member.spouse1_id)
            if spouse:
                info_row("配偶", spouse.name)
        if member.spouse2_id:
            spouse2 = self.member_map.get(member.spouse2_id)
            if spouse2:
                info_row("配偶2", spouse2.name)

        if member.bio:
            tk.Label(info_frame, text="简介：", font=("微软雅黑", 10, "bold"),
                     anchor="w").pack(pady=(10, 2))
            tk.Label(info_frame, text=member.bio, font=("微软雅黑", 9),
                     wraplength=450, justify="left", anchor="w").pack()

        btn_frame = tk.Frame(win)
        btn_frame.pack(pady=15)
        tk.Button(btn_frame, text="编辑", font=("微软雅黑", 10),
                  command=lambda: (win.destroy(), self.edit_member_dialog(member_id)),
                  bg="#3498db", fg="white", cursor="hand2").pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="删除", font=("微软雅黑", 10),
                  command=lambda: self.confirm_delete(member_id, win),
                  bg="#e74c3c", fg="white", cursor="hand2").pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="关闭", font=("微软雅黑", 10),
                  command=win.destroy).pack(side=tk.LEFT, padx=5)

    def confirm_delete(self, member_id, win):
        if messagebox.askyesno("确认删除", "确定删除该成员吗？"):
            delete_member(member_id)
            win.destroy()
            self.load_data()

    # ========== 添加/编辑成员 ==========
    def add_member_dialog(self):
        self._member_dialog(None)

    def edit_member_dialog(self, member_id):
        self._member_dialog(member_id)

    def _member_dialog(self, member_id):
        is_edit = member_id is not None
        member = self.member_map.get(member_id) if is_edit else None

        win = tk.Toplevel(self.root)
        win.title("编辑成员" if is_edit else "添加成员")
        win.geometry("550x700")
        win.transient(self.root)
        win.grab_set()

        # 变量
        name_var = tk.StringVar(value=member.name if member else "")
        gender_var = tk.StringVar(value=member.gender if member else "男")
        birth_var = tk.StringVar(value=member.birth_date if member else "")
        death_var = tk.StringVar(value=member.death_date if member else "")
        bio_var = tk.StringVar(value=member.bio if member else "")
        spouse_var = tk.StringVar()
        father_var = tk.StringVar(value=str(member.father_id) if member and member.father_id else "")
        mother_var = tk.StringVar(value=str(member.mother_id) if member and member.mother_id else "")
        photo_var = tk.StringVar(value=member.photo_path if member else "")

        form_frame = tk.Frame(win, padx=20, pady=10)
        form_frame.pack(fill=tk.BOTH, expand=True)

        # ===== 姓名 =====
        tk.Label(form_frame, text="姓名 *", font=("微软雅黑", 10),
                 anchor="e", width=12).grid(row=0, column=0, sticky="e", pady=5)
        name_entry = tk.Entry(form_frame, textvariable=name_var, font=("微软雅黑", 10), width=25)
        name_entry.grid(row=0, column=1, sticky="w", pady=5)

        # ===== 性别 =====
        tk.Label(form_frame, text="性别", font=("微软雅黑", 10),
                 anchor="e", width=12).grid(row=1, column=0, sticky="e", pady=5)
        gender_frame = tk.Frame(form_frame)
        gender_frame.grid(row=1, column=1, sticky="w", pady=5)
        tk.Radiobutton(gender_frame, text="男", variable=gender_var, value="男",
                       font=("微软雅黑", 10)).pack(side=tk.LEFT, padx=5)
        tk.Radiobutton(gender_frame, text="女", variable=gender_var, value="女",
                       font=("微软雅黑", 10)).pack(side=tk.LEFT, padx=5)

        # ===== 出生/逝世日期 =====
        tk.Label(form_frame, text="出生日期", font=("微软雅黑", 10),
                 anchor="e", width=12).grid(row=2, column=0, sticky="e", pady=5)
        tk.Entry(form_frame, textvariable=birth_var, font=("微软雅黑", 10),
                 width=25).grid(row=2, column=1, sticky="w", pady=5)

        tk.Label(form_frame, text="逝世日期", font=("微软雅黑", 10),
                 anchor="e", width=12).grid(row=3, column=0, sticky="e", pady=5)
        tk.Entry(form_frame, textvariable=death_var, font=("微软雅黑", 10),
                 width=25).grid(row=3, column=1, sticky="w", pady=5)

        # ===== 配偶（父母关系前面） =====
        tk.Label(form_frame, text="配偶", font=("微软雅黑", 10),
                 anchor="e", width=12).grid(row=4, column=0, sticky="e", pady=5)
        spouse_combo = ttk.Combobox(form_frame, font=("微软雅黑", 10), width=23)
        spouse_values = ["（无配偶）"] + [
            f"{m.id}. {m.name}（{m.gender or '未知'}，第{(m.generation or 0) + 1}代）"
            for m in self.members if m.id != member_id
        ]
        spouse_combo['values'] = spouse_values
        if member and member.spouse1_id and member.spouse1_id in self.member_map:
            spouse_obj = self.member_map[member.spouse1_id]
            spouse_combo.set(
                f"{member.spouse1_id}. {spouse_obj.name}（{spouse_obj.gender or '未知'}，第{(spouse_obj.generation or 0) + 1}代）"
            )
        spouse_combo.grid(row=4, column=1, sticky="w", pady=5)

        # ===== 配偶2（第二个配偶） =====
        tk.Label(form_frame, text="配偶2", font=("微软雅黑", 10),
                 anchor="e", width=12).grid(row=5, column=0, sticky="e", pady=5)
        spouse2_combo = ttk.Combobox(form_frame, font=("微软雅黑", 10), width=23)
        spouse2_values = ["（无配偶）"] + [
            f"{m.id}. {m.name}（{m.gender or '未知'}，第{(m.generation or 0) + 1}代）"
            for m in self.members if m.id != member_id
        ]
        spouse2_combo['values'] = spouse2_values
        if member and member.spouse2_id and member.spouse2_id in self.member_map:
            spouse2_obj = self.member_map[member.spouse2_id]
            spouse2_combo.set(
                f"{member.spouse2_id}. {spouse2_obj.name}（{spouse2_obj.gender or '未知'}，第{(spouse2_obj.generation or 0) + 1}代）"
            )
        spouse2_combo.grid(row=5, column=1, sticky="w", pady=5)

        # ===== 父亲 =====
        tk.Label(form_frame, text="父亲", font=("微软雅黑", 10),
                 anchor="e", width=12).grid(row=6, column=0, sticky="e", pady=5)
        father_combo = ttk.Combobox(form_frame, font=("微软雅黑", 10), width=23)
        father_values = [""] + [
            f"{m.id}. {m.name}" for m in self.members
            if m.id != member_id and m.gender == "男"
        ]
        father_combo['values'] = father_values
        if member and member.father_id and member.father_id in self.member_map:
            father_combo.set(f"{member.father_id}. {self.member_map[member.father_id].name}")
        father_combo.grid(row=6, column=1, sticky="w", pady=5)

        # ===== 母亲 =====
        tk.Label(form_frame, text="母亲", font=("微软雅黑", 10),
                 anchor="e", width=12).grid(row=7, column=0, sticky="e", pady=5)
        mother_combo = ttk.Combobox(form_frame, font=("微软雅黑", 10), width=23)
        mother_values = [""] + [
            f"{m.id}. {m.name}" for m in self.members
            if m.id != member_id and m.gender == "女"
        ]
        mother_combo['values'] = mother_values
        if member and member.mother_id and member.mother_id in self.member_map:
            mother_combo.set(f"{member.mother_id}. {self.member_map[member.mother_id].name}")
        mother_combo.grid(row=7, column=1, sticky="w", pady=5)

        # ===== 照片 =====
        tk.Label(form_frame, text="寸照", font=("微软雅黑", 10),
                 anchor="e", width=12).grid(row=8, column=0, sticky="e", pady=5)
        photo_main_frame = tk.Frame(form_frame)
        photo_main_frame.grid(row=8, column=1, sticky="w", pady=5)
        # 上传行
        upload_frame = tk.Frame(photo_main_frame)
        upload_frame.pack(side=tk.LEFT)
        tk.Entry(upload_frame, textvariable=photo_var, font=("微软雅黑", 10),
                 width=20).pack(side=tk.LEFT)
        tk.Button(upload_frame, text="选择图片", font=("微软雅黑", 9),
                  command=lambda: self.select_photo(photo_var, photo_preview_label),
                  cursor="hand2").pack(side=tk.LEFT, padx=5)
        # 预览标签（位于上传行下方）
        photo_preview_label = tk.Label(photo_main_frame, text="[无照片]" if not (member and member.photo_path) else "",
                                       font=("微软雅黑", 8), bg="#eee", width=12, height=6,
                                       anchor="center", justify="center")
        photo_preview_label.pack(side=tk.LEFT, padx=(10, 0))
        # 编辑时：已有照片则立即显示
        if member and member.photo_path and os.path.exists(member.photo_path):
            try:
                img = Image.open(member.photo_path)
                img = img.resize((80, 100), Image.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                photo_preview_label.config(image=photo, text="")
                photo_preview_label.image = photo
            except:
                pass

        # ===== 简介 =====
        tk.Label(form_frame, text="个人简介", font=("微软雅黑", 10),
                 anchor="e", width=12).grid(row=9, column=0, sticky="ne", pady=5)
        bio_text = tk.Text(form_frame, font=("微软雅黑", 10), width=30, height=4)
        bio_text.grid(row=9, column=1, sticky="w", pady=5)
        if member:
            bio_text.insert("1.0", member.bio or "")

        # ===== 保存 =====
        def save():
            name = name_var.get().strip()
            if not name:
                messagebox.showwarning("提示", "姓名为必填项")
                return

            spouse1_id = None
            spouse2_id = None
            father_id = None
            mother_id = None

            try:
                if spouse_combo.get().strip() and spouse_combo.get().strip() != "（无配偶）":
                    spouse1_id = int(spouse_combo.get().strip().split(".")[0])
            except:
                pass

            try:
                if spouse2_combo.get().strip() and spouse2_combo.get().strip() != "（无配偶）":
                    spouse2_id = int(spouse2_combo.get().strip().split(".")[0])
            except:
                pass

            try:
                if father_combo.get().strip():
                    father_id = int(father_combo.get().strip().split(".")[0])
            except:
                pass

            try:
                if mother_combo.get().strip():
                    mother_id = int(mother_combo.get().strip().split(".")[0])
            except:
                pass

            data = {
                'name': name,
                'gender': gender_var.get(),
                'birth_date': birth_var.get().strip() or None,
                'death_date': death_var.get().strip() or None,
                'father_id': father_id,
                'mother_id': mother_id,
                'spouse1_id': spouse1_id,
                'spouse2_id': spouse2_id,
                'bio': bio_text.get("1.0", tk.END).strip(),
                'photo_path': photo_var.get().strip() or None,
                'extra_photos': member.extra_photos if member else []
            }

            new_id = save_member(data, member_id)

            # 双向配偶关系
            def _set_spouse(target_id, self_id):
                if not target_id:
                    return
                conn = get_conn()
                c = conn.cursor()
                c.execute("SELECT spouse1_id, spouse2_id FROM members WHERE id=?", (target_id,))
                row = c.fetchone()
                if row:
                    if row[0] is None:
                        c.execute("UPDATE members SET spouse1_id=? WHERE id=?", (self_id, target_id))
                    elif row[1] is None:
                        c.execute("UPDATE members SET spouse2_id=? WHERE id=?", (self_id, target_id))
                conn.commit()
                conn.close()

            saved_id = new_id if not is_edit else member_id
            if spouse1_id:
                _set_spouse(spouse1_id, saved_id)
            if spouse2_id:
                _set_spouse(spouse2_id, saved_id)

            win.destroy()
            self.load_data()
            messagebox.showinfo("成功", "保存成功！")

        btn_frame = tk.Frame(win)
        btn_frame.pack(pady=15)
        tk.Button(btn_frame, text="保存", font=("微软雅黑", 10),
                  command=save, bg="#27ae60", fg="white",
                  cursor="hand2", width=12).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="取消", font=("微软雅黑", 10),
                  command=win.destroy, width=12).pack(side=tk.LEFT, padx=5)

    def select_photo(self, var, preview_label=None):
        path = filedialog.askopenfilename(
            title="选择照片",
            filetypes=[("图片文件", "*.jpg *.jpeg *.png *.bmp"), ("所有文件", "*.*")]
        )
        if path:
            var.set(path)
            # 实时更新预览
            if preview_label:
                self._update_photo_preview(preview_label, path)

    def _update_photo_preview(self, label, path):
        """更新照片预览标签"""
        try:
            if path and os.path.exists(path):
                img = Image.open(path)
                img = img.resize((80, 100), Image.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                label.config(image=photo, text="")
                label.image = photo  # 保持引用，防止被GC回收
            else:
                label.config(image="", text="[无照片]")
                label.image = None
        except Exception:
            label.config(image="", text="[照片加载失败]")
            label.image = None

    # ========== 家谱树 ==========
    def draw_tree(self):
        self.tree_canvas.delete("all")
        self.canvas_items.clear()
        self.tree_photo_images.clear()

        if not self.members:
            self.tree_canvas.create_text(400, 300, text="暂无成员，请添加成员开始",
                                          font=("微软雅黑", 14), fill="#999")
            return

        roots = [m for m in self.members if m.father_id is None and m.mother_id is None]
        if not roots:
            roots = [self.members[0]]

        generations = {}
        for m in self.members:
            gen = m.generation if m.generation is not None else 0
            generations.setdefault(gen, []).append(m)

        node_positions = {}
        nw = self.node_width + 30
        nh = self.level_height

        for gen, members in sorted(generations.items()):
            y = gen * nh + 40
            total_width = len(members) * nw
            start_x = max(100, (1500 - total_width) // 2)
            for i, m in enumerate(members):
                x = start_x + i * nw + nw // 2
                node_positions[m.id] = (x, y)

        if node_positions:
            max_x = max(x for x, y in node_positions.values()) + 100
            max_y = max(y for x, y in node_positions.values()) + 100
        else:
            max_x, max_y = 800, 600

        self.tree_canvas.config(scrollregion=(0, 0, max_x, max_y))

        for m in self.members:
            if m.father_id and m.father_id in node_positions and m.id in node_positions:
                px, py = node_positions[m.father_id]
                cx, cy = node_positions[m.id]
                mid_y = (py + cy) // 2
                self.tree_canvas.create_line(
                    px, py + self.node_height // 2,
                    px, mid_y,
                    cx, mid_y,
                    cx, cy - self.node_height // 2,
                    fill="#7f8c8d", width=2
                )
            elif m.mother_id and m.mother_id in node_positions and m.id in node_positions:
                px, py = node_positions[m.mother_id]
                cx, cy = node_positions[m.id]
                mid_y = (py + cy) // 2
                self.tree_canvas.create_line(
                    px, py + self.node_height // 2,
                    px, mid_y,
                    cx, mid_y,
                    cx, cy - self.node_height // 2,
                    fill="#e74c3c", width=2, dash=(4, 2)
                )
            if m.spouse1_id and m.spouse1_id in node_positions and m.id in node_positions:
                sx, sy = node_positions[m.spouse1_id]
                cx2, cy2 = node_positions[m.id]
                self.tree_canvas.create_line(
                    sx + self.node_width // 2, sy,
                    cx2 - self.node_width // 2, cy2,
                    fill="#f39c12", width=2, dash=(6, 3)
                )
            if m.spouse2_id and m.spouse2_id in node_positions and m.id in node_positions:
                sx2, sy2 = node_positions[m.spouse2_id]
                cx2, cy2 = node_positions[m.id]
                self.tree_canvas.create_line(
                    sx2 + self.node_width // 2, sy2,
                    cx2 - self.node_width // 2, cy2,
                    fill="#e67e22", width=2, dash=(6, 3)
                )

        for m in self.members:
            if m.id not in node_positions:
                continue
            x, y = node_positions[m.id]
            self._draw_node(m, x, y)

        if node_positions:
            avg_x = sum(x for x, y in node_positions.values()) / len(node_positions)
            avg_y = sum(y for x, y in node_positions.values()) / len(node_positions)
            self.tree_canvas.xview_moveto(max(0, (avg_x - 400) / max(max_x, 1)))
            self.tree_canvas.yview_moveto(max(0, (avg_y - 300) / max(max_y, 1)))

    def _draw_node(self, member, x, y):
        nw = self.node_width
        nh = self.node_height

        if member.death_date:
            bg_color = "#95a5a6"
        elif member.gender == "男":
            bg_color = "#3498db"
        elif member.gender == "女":
            bg_color = "#e91e63"
        else:
            bg_color = "#9b59b6"

        tag = f"node_{member.id}"
        self.tree_canvas.create_rectangle(
            x - nw // 2, y - nh // 2,
            x + nw // 2, y + nh // 2,
            fill=bg_color, outline="#2c3e50", width=2,
            tags=tag
        )

        # 1寸照片尺寸（36x48px，标准1寸证件照比例）
        photo_w = 36
        photo_h = 48
        photo_x = x - nw // 2 + 6
        photo_y = y - photo_h // 2

        if member.photo_path and os.path.exists(member.photo_path):
            try:
                img = Image.open(member.photo_path)
                img = img.resize((photo_w, photo_h), Image.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                self.tree_photo_images[member.id] = photo
                self.tree_canvas.create_image(
                    photo_x, photo_y,
                    image=photo, anchor="nw", tags=tag
                )
            except:
                # 读取失败也画空白占位
                self.tree_canvas.create_rectangle(
                    photo_x, photo_y,
                    photo_x + photo_w, photo_y + photo_h,
                    fill="#ddd", outline="#aaa", width=1, tags=tag
                )
        else:
            # 无照片 → 画空白1寸占位（浅灰背景+虚线边框）
            self.tree_canvas.create_rectangle(
                photo_x, photo_y,
                photo_x + photo_w, photo_y + photo_h,
                fill="#ddd", outline="#aaa", width=1, tags=tag
            )
            # 加灰色人物图标占位符（简单"X"表示无照片）
            mid_x = photo_x + photo_w // 2
            mid_y = photo_y + photo_h // 2
            self.tree_canvas.create_text(
                mid_x, mid_y,
                text="○",
                font=("Arial", 14),
                fill="#aaa",
                tags=tag
            )

        # 姓名和代际文字放在右侧
        text_x = x + photo_w // 2 + 10
        self.tree_canvas.create_text(
            text_x, y - 8, text=member.name,
            font=("微软雅黑", 11, "bold"), fill="white",
            tags=tag
        )

        self.tree_canvas.create_text(
            text_x, y + 12,
            text=f"第{member.generation + 1}代" if member.generation is not None else "",
            font=("微软雅黑", 8), fill="#eee",
            tags=tag
        )

        def on_click(event, mid=member.id):
            self.show_member_detail(mid)

        self.tree_canvas.tag_bind(tag, "<Button-1>", on_click)
        self.canvas_items[member.id] = tag

    def zoom_tree(self, factor):
        self.scale *= factor
        self.scale = max(0.3, min(3.0, self.scale))
        self.tree_canvas.scale("all",
                                self.tree_canvas.winfo_width() // 2,
                                self.tree_canvas.winfo_height() // 2,
                                factor, factor)

    # ========== 照片墙 ==========
    def show_photo_wall(self):
        win = tk.Toplevel(self.root)
        win.title("照片墙")
        win.geometry("900x700")
        win.transient(self.root)

        top_bar = tk.Frame(win, bg="#f0f0f0")
        top_bar.pack(fill=tk.X, padx=10, pady=8)
        tk.Button(top_bar, text="上传照片", font=("微软雅黑", 10),
                  command=lambda: self.upload_wall_photo(win),
                  bg="#27ae60", fg="white", cursor="hand2").pack(side=tk.LEFT, padx=5)
        tk.Button(top_bar, text="刷新", font=("微软雅黑", 10),
                  command=lambda: self._refresh_photo_wall(win),
                  bg="#3498db", fg="white", cursor="hand2").pack(side=tk.LEFT)

        canvas = tk.Canvas(win, bg="#f0f0f0")
        scrollbar = tk.Scrollbar(win, orient=tk.VERTICAL, command=canvas.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        canvas.config(yscrollcommand=scrollbar.set)

        inner = tk.Frame(canvas, bg="#f0f0f0")
        canvas.create_window((0, 0), window=inner, anchor="nw")

        def on_scroll(event):
            canvas.yview_scroll(-1 * (event.delta // 120), tk.UNITS)
        canvas.bind_all("<MouseWheel>", on_scroll)

        wall_photos = get_all_wall_photos()
        self.wall_photo_images.clear()

        if not wall_photos:
            tk.Label(inner, text="暂无照片，点击上方「上传照片」添加",
                     font=("微软雅黑", 14), fg="#999", bg="#f0f0f0").pack(pady=50)
        else:
            for i, p in enumerate(wall_photos):
                row = i // 4
                col = i % 4
                cell = tk.Frame(inner, bg="white", bd=1, relief=tk.RIDGE)
                cell.grid(row=row, column=col, padx=8, pady=8, sticky="n")

                if os.path.exists(p.file_path):
                    try:
                        img = Image.open(p.file_path)
                        img = img.resize((180, 220), Image.LANCZOS)
                        photo = ImageTk.PhotoImage(img)
                        self.wall_photo_images[p.id] = photo
                        tk.Label(cell, image=photo, bg="white").pack()
                    except:
                        tk.Label(cell, text="[图片加载失败]", bg="#eee",
                                 width=20, height=12).pack()
                else:
                    tk.Label(cell, text="[文件不存在]", bg="#eee",
                             width=20, height=12).pack()

                linked_name = ""
                if p.member_id and p.member_id in self.member_map:
                    linked_name = self.member_map[p.member_id].name
                caption_text = p.caption or ""
                if linked_name:
                    display_text = linked_name
                    if caption_text:
                        display_text += f"\n{caption_text[:20]}"
                else:
                    display_text = caption_text[:30] if caption_text else ""

                tk.Label(cell, text=display_text, font=("微软雅黑", 9, "bold"),
                         bg="white", wraplength=170).pack(pady=3)

                tk.Button(cell, text="删除", font=("微软雅黑", 8),
                          command=lambda pid=p.id, w=win: self._do_delete_photo(pid, w),
                          bg="#e74c3c", fg="white", cursor="hand2").pack(pady=2)

        inner.update_idletasks()
        canvas.config(scrollregion=canvas.bbox("all"))

    def upload_wall_photo(self, parent_win):
        path = filedialog.askopenfilename(
            title="选择照片",
            filetypes=[("图片文件", "*.jpg *.jpeg *.png *.bmp *.gif"), ("所有文件", "*.*")]
        )
        if not path:
            return

        ext = os.path.splitext(path)[1].lower()
        filename = f"wall_{datetime.now().strftime('%Y%m%d%H%M%S')}{ext}"
        dest_path = os.path.join(PHOTO_DIR, filename)

        try:
            shutil.copy2(path, dest_path)
        except Exception as e:
            messagebox.showerror("错误", f"复制文件失败：{e}")
            return

        sel_win = tk.Toplevel(self.root)
        sel_win.title("关联成员")
        sel_win.geometry("400x200")
        sel_win.transient(self.root)
        sel_win.grab_set()

        tk.Label(sel_win, text="是否为照片关联家族成员？（可选）",
                 font=("微软雅黑", 11)).pack(pady=15)

        member_var = tk.StringVar(value="（不关联成员）")
        member_combo = ttk.Combobox(sel_win, textvariable=member_var,
                                     values=["（不关联成员）"] + [
                                         f"{m.id}. {m.name}" for m in self.members
                                     ],
                                     font=("微软雅黑", 10), state="readonly", width=30)
        member_combo.pack(pady=10)

        tk.Label(sel_win, text="照片说明", font=("微软雅黑", 10)).pack(pady=5)
        # 默认用原文件名（去扩展名）作为说明
        default_caption = os.path.splitext(os.path.basename(path))[0]
        caption_entry = tk.Entry(sel_win, font=("微软雅黑", 10), width=40)
        caption_entry.insert(0, default_caption)
        caption_entry.pack(pady=5)

        def do_save():
            selected = member_var.get()
            linked_member_id = None
            if selected and selected != "（不关联成员）":
                try:
                    linked_member_id = int(selected.split(".")[0])
                except:
                    pass

            caption = caption_entry.get().strip()

            conn = get_conn()
            c = conn.cursor()
            c.execute(
                "INSERT INTO photo_wall (file_path, caption, member_id) VALUES (?, ?, ?)",
                (dest_path, caption or None, linked_member_id)
            )
            conn.commit()
            conn.close()

            sel_win.destroy()
            self._refresh_photo_wall(parent_win)

        tk.Button(sel_win, text="保存", font=("微软雅黑", 10),
                  command=do_save, bg="#27ae60", fg="white",
                  cursor="hand2").pack(pady=10)

    def _refresh_photo_wall(self, win):
        """重新渲染照片墙内容"""
        # 找到 inner frame 并清空重建
        for widget in win.winfo_children():
            if isinstance(widget, tk.Canvas):
                inner_frame = widget.winfo_children()[0] if widget.winfo_children() else None
                if inner_frame:
                    for child in inner_frame.winfo_children():
                        child.destroy()

                    wall_photos = get_all_wall_photos()

                    if not wall_photos:
                        tk.Label(inner_frame, text="暂无照片，点击上方「上传照片」添加",
                                 font=("微软雅黑", 14), fg="#999", bg="#f0f0f0").pack(pady=50)
                    else:
                        for i, p in enumerate(wall_photos):
                            row = i // 4
                            col = i % 4
                            cell = tk.Frame(inner_frame, bg="white", bd=1, relief=tk.RIDGE)
                            cell.grid(row=row, column=col, padx=8, pady=8, sticky="n")

                            if os.path.exists(p.file_path):
                                try:
                                    img = Image.open(p.file_path)
                                    img = img.resize((180, 220), Image.LANCZOS)
                                    photo = ImageTk.PhotoImage(img)
                                    self.wall_photo_images[p.id] = photo
                                    tk.Label(cell, image=photo, bg="white").pack()
                                except:
                                    tk.Label(cell, text="[图片加载失败]", bg="#eee",
                                             width=20, height=12).pack()
                            else:
                                tk.Label(cell, text="[文件不存在]", bg="#eee",
                                         width=20, height=12).pack()

                            linked_name = ""
                            if p.member_id and p.member_id in self.member_map:
                                linked_name = self.member_map[p.member_id].name
                            caption_text = p.caption or ""
                            if linked_name:
                                display_text = linked_name
                                if caption_text:
                                    display_text += f"\n{caption_text[:20]}"
                            else:
                                display_text = caption_text[:30] if caption_text else ""

                            tk.Label(cell, text=display_text, font=("微软雅黑", 9, "bold"),
                                     bg="white", wraplength=170).pack(pady=3)

                            tk.Button(cell, text="删除", font=("微软雅黑", 8),
                                      command=lambda pid=p.id, w=win: self._do_delete_photo(pid, w),
                                      bg="#e74c3c", fg="white", cursor="hand2").pack(pady=2)

                    inner_frame.update_idletasks()
                    widget.config(scrollregion=widget.bbox("all"))
                break

    def _do_delete_photo(self, photo_id, win):
        if messagebox.askyesno("确认", "确定删除该照片？"):
            delete_wall_photo(photo_id)
            self._refresh_photo_wall(win)

    def _refresh_photo_wall(self, win):
        for widget in win.winfo_children():
            widget.destroy()
        self.show_photo_wall()

    # ========== CSV 导入/导出 ==========
    def download_template(self):
        """下载导入模板 CSV"""
        path = filedialog.asksaveasfilename(
            title="保存导入模板",
            defaultextension=".csv",
            filetypes=[("CSV文件", "*.csv")],
            initialfile="家谱导入模板.csv"
        )
        if not path:
            return

        headers = ["姓名", "性别", "出生日期", "逝世日期", "父亲姓名", "母亲姓名", "配偶1姓名", "配偶2姓名", "个人简介", "寸照路径"]
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            # 写两行示例
            writer.writerow(["关国安", "男", "1950-01", "", "关大海", "王秀英", "", "", "家族长辈", "photos/guanguoan.jpg"])
            writer.writerow(["关星星", "男", "1980-05", "", "关国安", "王双连", "李梅", "", "关家长子", ""])

        messagebox.showinfo("成功", f"模板已保存：\n{path}\n\n请用 Excel 打开，按格式填写后导入。")

    def export_members_csv(self):
        """导出所有成员为 CSV"""
        if not self.members:
            messagebox.showwarning("提示", "没有成员数据可导出")
            return

        path = filedialog.asksaveasfilename(
            title="导出成员CSV",
            defaultextension=".csv",
            filetypes=[("CSV文件", "*.csv")],
            initialfile="家谱成员导出.csv"
        )
        if not path:
            return

        headers = ["姓名", "性别", "出生日期", "逝世日期", "父亲姓名", "母亲姓名", "配偶1姓名", "配偶2姓名", "个人简介", "寸照路径"]
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            for m in self.members:
                father_name = self.member_map[m.father_id].name if m.father_id and m.father_id in self.member_map else ""
                mother_name = self.member_map[m.mother_id].name if m.mother_id and m.mother_id in self.member_map else ""
                spouse1_name = self.member_map[m.spouse1_id].name if m.spouse1_id and m.spouse1_id in self.member_map else ""
                spouse2_name = self.member_map[m.spouse2_id].name if m.spouse2_id and m.spouse2_id in self.member_map else ""
                writer.writerow([
                    m.name,
                    m.gender or "",
                    m.birth_date or "",
                    m.death_date or "",
                    father_name,
                    mother_name,
                    spouse1_name,
                    spouse2_name,
                    m.bio or "",
                    m.photo_path or ""
                ])

        messagebox.showinfo("成功", f"已导出 {len(self.members)} 位成员：\n{path}")

    def import_members_csv(self):
        """从 CSV 导入成员"""
        path = filedialog.askopenfilename(
            title="选择导入文件",
            filetypes=[("CSV文件", "*.csv"), ("所有文件", "*.*")]
        )
        if not path:
            return

        # 自动检测编码：优先UTF-8，失败则用GBK
        encodings = ['utf-8-sig', 'gbk', 'gb2312']
        rows = None
        last_err = None
        for enc in encodings:
            try:
                with open(path, 'r', encoding=enc) as f:
                    reader = csv.reader(f)
                    rows = list(reader)
                break
            except Exception as e:
                last_err = e
                continue
        if rows is None:
            messagebox.showerror('错误', f'读取文件失败：{last_err}')
            return

        if len(rows) < 2:
            messagebox.showwarning("提示", "CSV 文件内容为空或只有表头")
            return

        header = rows[0]
        expected = ["姓名", "性别", "出生日期", "逝世日期", "父亲姓名", "母亲姓名", "配偶1姓名", "配偶2姓名", "个人简介", "寸照路径"]
        if header != expected:
            messagebox.showwarning("提示", f"表头格式不对，请使用「下载导入模板」生成的文件。\n\n期望：{expected}\n实际：{header}")
            return

        data_rows = rows[1:]
        data_rows = [r for r in data_rows if r and r[0].strip()]

        if not data_rows:
            messagebox.showwarning("提示", "没有可导入的数据行")
            return

        # 构建姓名→ID 映射（现有成员）
        name_to_id = {m.name: m.id for m in self.members}
        imported = 0
        skipped = 0
        errors = []

        for i, row in enumerate(data_rows, start=2):
            try:
                name = row[0].strip()
                if not name:
                    skipped += 1
                    continue

                gender = row[1].strip() if len(row) > 1 else ""
                birth_date = row[2].strip() if len(row) > 2 else ""
                death_date = row[3].strip() if len(row) > 3 else ""
                father_name = row[4].strip() if len(row) > 4 else ""
                mother_name = row[5].strip() if len(row) > 5 else ""
                spouse1_name = row[6].strip() if len(row) > 6 else ""
                spouse2_name = row[7].strip() if len(row) > 7 else ""
                bio = row[8].strip() if len(row) > 8 else ""
                photo_path = row[9].strip() if len(row) > 9 else ""

                # 检查是否已存在（已存在则跳过，不覆盖现有数据）
                if name in name_to_id:
                    skipped += 1
                    continue

                father_id = name_to_id.get(father_name) if father_name else None
                mother_id = name_to_id.get(mother_name) if mother_name else None
                spouse1_id = name_to_id.get(spouse1_name) if spouse1_name else None
                spouse2_id = name_to_id.get(spouse2_name) if spouse2_name else None

                data = {
                    'name': name,
                    'gender': gender or None,
                    'birth_date': birth_date or None,
                    'death_date': death_date or None,
                    'father_id': father_id,
                    'mother_id': mother_id,
                    'spouse1_id': spouse1_id,
                    'spouse2_id': spouse2_id,
'bio': bio,
                    'photo_path': photo_path or None,
                    'extra_photos': []
                }

                new_id = save_member(data, member_id=None)
                name_to_id[name] = new_id
                imported += 1
            except Exception as e:
                errors.append(f"第{i}行：{e}")
                skipped += 1

        # 双向配偶关联
        conn = get_conn()
        c = conn.cursor()
        for name, member_id in name_to_id.items():
            if member_id > max(self.member_map.keys(), default=0):
                c.execute("SELECT spouse1_id, spouse2_id FROM members WHERE id=?", (member_id,))
                row = c.fetchone()
                if row:
                    for sid in (row[0], row[1]):
                        if sid and sid not in (row[0], row[1]):
                            c.execute("SELECT spouse1_id, spouse2_id FROM members WHERE id=?", (sid,))
                            srow = c.fetchone()
                            if srow:
                                if srow[0] is None:
                                    c.execute("UPDATE members SET spouse1_id=? WHERE id=?", (member_id, sid))
                                elif srow[1] is None:
                                    c.execute("UPDATE members SET spouse2_id=? WHERE id=?", (member_id, sid))
        conn.commit()
        conn.close()

        self.load_data()

        msg = f"导入完成！\n成功：{imported} 人\n跳过：{skipped} 人"
        if errors:
            msg += f"\n错误：{len(errors)} 条\n" + "\n".join(errors[:5])
        messagebox.showinfo("导入结果", msg)

    # ========== HTML 导出 ==========
    def export_html(self):
        if not self.members:
            messagebox.showwarning("提示", "没有成员数据可导出")
            return

        path = filedialog.asksaveasfilename(
            title="保存家谱HTML",
            defaultextension=".html",
            filetypes=[("HTML文件", "*.html")],
            initialfile="家谱.html"
        )
        if not path:
            return

        try:
            self._generate_html(path)
            messagebox.showinfo("成功", f"已导出至：\n{path}\n请用浏览器打开并打印为PDF")
        except Exception as e:
            messagebox.showerror("错误", f"导出失败：{e}")

    def _generate_html(self, path):
        generations = {}
        for m in self.members:
            gen = m.generation if m.generation is not None else 0
            generations.setdefault(gen, []).append(m)

        html = []
        html.append("<!DOCTYPE html>")
        html.append("<html lang='zh-CN'>")
        html.append("<head>")
        html.append("<meta charset='UTF-8'>")
        html.append(f"<title>家谱 - {datetime.now().strftime('%Y年%m月%d日')}</title>")
        html.append("<style>")
        html.append("""
            * { box-sizing: border-box; margin: 0; padding: 0; }
            body { font-family: 'Microsoft YaHei', sans-serif; background: #faf8f5; color: #333; }
            .cover { text-align: center; padding: 80px 20px; background: linear-gradient(135deg, #2c3e50, #34495e); color: white; min-height: 100vh; display: flex; flex-direction: column; justify-content: center; }
            .cover h1 { font-size: 3em; margin-bottom: 20px; letter-spacing: 8px; }
            .cover p { font-size: 1.2em; color: #bdc3c7; }
            .cover .date { margin-top: 40px; font-size: 1em; color: #95a5a6; }
            .section { max-width: 1000px; margin: 40px auto; padding: 0 20px; }
            .section-title { font-size: 1.8em; color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; margin-bottom: 30px; }
            .tree-container { overflow-x: auto; padding: 20px 0; }
            .tree-table { border-collapse: separate; border-spacing: 20px 30px; margin: 0 auto; }
            .member-card { background: white; border-radius: 12px; padding: 15px; width: 160px; text-align: center; box-shadow: 0 2px 8px rgba(0,0,0,0.1); transition: transform 0.2s; }
            .member-card:hover { transform: translateY(-3px); box-shadow: 0 4px 16px rgba(0,0,0,0.15); }
            .member-card .photo { width: 80px; height: 80px; border-radius: 50%; object-fit: cover; margin: 0 auto 10px; border: 3px solid #3498db; }
            .member-card .name { font-size: 1.1em; font-weight: bold; margin-bottom: 5px; }
            .member-card .info { font-size: 0.8em; color: #777; }
            .member-card .male { border-color: #3498db; }
            .member-card .female { border-color: #e91e63; }
            .member-card .deceased { opacity: 0.7; }
            .photo-wall { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 15px; }
            .photo-item { background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 6px rgba(0,0,0,0.1); }
            .photo-item img { width: 100%; height: 200px; object-fit: cover; }
            .photo-item .caption { padding: 10px; font-size: 0.9em; }
            .photo-item .caption strong { display: block; margin-bottom: 3px; }
            .photo-item .caption small { color: #777; }
            .member-list { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 15px; }
            .member-detail { background: white; border-radius: 8px; padding: 15px; box-shadow: 0 1px 4px rgba(0,0,0,0.1); }
            .member-detail h3 { color: #2c3e50; margin-bottom: 8px; }
            .member-detail p { font-size: 0.9em; color: #555; margin: 3px 0; }
            .gen-table { width: 100%; border-collapse: collapse; margin-bottom: 30px; background: white; box-shadow: 0 1px 4px rgba(0,0,0,0.08); }
            .gen-table th { background: #34495e; color: white; padding: 10px 12px; text-align: center; font-size: 0.95em; }
            .gen-table td { padding: 8px 12px; text-align: center; font-size: 0.9em; border-bottom: 1px solid #ecf0f1; vertical-align: middle; }
            .gen-table tbody tr:nth-child(even) { background: #f8f9fa; }
            .gen-table tbody tr:hover { background: #eaf2ff; }
            .gen-table td:first-child { font-weight: bold; color: #2c3e50; }
            .gen-table td:last-child { text-align: left; color: #555; }
            .footer { text-align: center; padding: 40px; color: #999; font-size: 0.9em; }
            @media print { body { background: white; } .member-card { break-inside: avoid; } }
        """)
        html.append("</style>")
        html.append("</head>")
        html.append("<body>")

        html.append("<div class='cover'>")
        html.append("<h1>家谱</h1>")
        html.append(f"<p>共 {len(self.members)} 位家族成员</p>")
        html.append(f"<p class='date'>编制日期：{datetime.now().strftime('%Y年%m月%d日')}</p>")
        html.append("</div>")

        html.append("<div class='section'>")
        html.append("<h2 class='section-title'>世系图</h2>")
        html.append("<div class='tree-container'>")
        html.append("<table class='tree-table'>")

        for gen in sorted(generations.keys()):
            members = generations[gen]
            html.append("<tr>")
            for m in members:
                photo_tag = ""
                if m.photo_path and os.path.exists(m.photo_path):
                    try:
                        with open(m.photo_path, "rb") as f:
                            img_data = base64.b64encode(f.read()).decode()
                            ext = m.photo_path.split(".")[-1].lower()
                            mime = "image/jpeg" if ext in ("jpg", "jpeg") else "image/png"
                            photo_tag = f"<img class='photo' src='data:{mime};base64,{img_data}'>"
                    except:
                        pass

                gender_class = ""
                if m.gender == "男":
                    gender_class = "male"
                elif m.gender == "女":
                    gender_class = "female"
                if m.death_date:
                    gender_class += " deceased"

                birth_info = f"{m.birth_date}" if m.birth_date else ""
                death_info = f" ~ {m.death_date}" if m.death_date else "（在世）"

                html.append(f"""
                <td>
                    <div class='member-card {gender_class}'>
                        {photo_tag}
                        <div class='name'>{m.name}</div>
                        <div class='info'>{birth_info}{death_info}</div>
                    </div>
                </td>
                """)
            html.append("</tr>")

        html.append("</table>")
        html.append("</div>")
        html.append("</div>")

        html.append("<div class='section'>")
        html.append("<h2 class='section-title'>成员详情</h2>")

        # 按世代分组，每组一个表格
        for gen in sorted(generations.keys(), reverse=True):
            members = sorted(generations[gen], key=lambda x: x.name)
            html.append(f"<h3 style='color:#2c3e50;margin:25px 0 10px;'>第{gen + 1}代</h3>")
            html.append("<table class='gen-table'>")
            html.append("<thead><tr><th>姓名</th><th>生卒年份</th><th>代际</th><th>关系</th><th>配偶/备注</th></tr></thead>")
            html.append("<tbody>")

            for m in members:
                birth = m.birth_date or ""
                death = m.death_date or "在世"
                life = f"{birth} - {death}"

                gen_label = f"第{gen + 1}代"

                # 关系逻辑：父母在谱内 -> 和xxx的儿子/女儿；父母不在但配偶在 -> xxx的丈夫/妻子
                relation = ""
                if m.father_id and m.father_id in self.member_map:
                    father = self.member_map[m.father_id]
                    if m.mother_id and m.mother_id in self.member_map:
                        mother = self.member_map[m.mother_id]
                        relation = father.name + "和" + mother.name + ("的儿子" if m.gender == "男" else "的女儿")
                    else:
                        relation = father.name + ("的儿子" if m.gender == "男" else "的女儿")
                elif m.mother_id and m.mother_id in self.member_map:
                    mother = self.member_map[m.mother_id]
                    relation = mother.name + ("的儿子" if m.gender == "男" else "的女儿")
                else:
                    for sid_key in ('spouse1_id', 'spouse2_id'):
                        sid = getattr(m, sid_key, None)
                        if sid and sid in self.member_map:
                            spouse = self.member_map[sid]
                            relation = spouse.name + ("的丈夫" if m.gender == "女" else "的妻子")
                            break

                spouse_note = ""
                for sid_key in ('spouse1_id', 'spouse2_id'):
                    sid = getattr(m, sid_key, None)
                    if sid and sid in self.member_map:
                        sname = self.member_map[sid].name
                        spouse_note += (sname + "；") if spouse_note else (sname + "；")
                if m.bio:
                    spouse_note += ("；" + m.bio) if spouse_note else m.bio

                html.append(f"<tr>")
                html.append(f"<td><strong>{m.name}</strong></td>")
                html.append(f"<td>{life}</td>")
                html.append(f"<td>{gen_label}</td>")
                html.append(f"<td>{relation}</td>")
                html.append(f"<td>{spouse_note}</td>")
                html.append(f"</tr>")

            html.append("</tbody></table>")
        html.append("</div>")

        all_photos = []
        for m in self.members:
            if m.photo_path and os.path.exists(m.photo_path):
                all_photos.append((m.photo_path, m.name, m.bio))
        wall_photos = get_all_wall_photos()
        for p in wall_photos:
            if os.path.exists(p.file_path):
                linked_name = self.member_map[p.member_id].name if p.member_id and p.member_id in self.member_map else ""
                all_photos.append((p.file_path, linked_name, p.caption))

        if all_photos:
            html.append("<div class='section'>")
            html.append("<h2 class='section-title'>照片墙</h2>")
            html.append("<div class='photo-wall'>")
            for photo_path, linked_name, caption in all_photos:
                try:
                    with open(photo_path, "rb") as f:
                        img_data = base64.b64encode(f.read()).decode()
                        ext = photo_path.split(".")[-1].lower()
                        mime = "image/jpeg" if ext in ("jpg", "jpeg") else "image/png"
                    bio_short = (caption[:40] + "...") if caption and len(caption) > 40 else (caption or "")
                    html.append(f"""
                    <div class='photo-item'>
                        <img src='data:{mime};base64,{img_data}'>
                        <div class='caption'>
                            <strong>{linked_name}</strong>
                            <small>{bio_short}</small>
                        </div>
                    </div>
                    """)
                except:
                    pass
            html.append("</div>")
            html.append("</div>")

        html.append("<div class='footer'>")
        html.append(f"<p>家谱制作工具 v1.9.2 | 编制于 {datetime.now().strftime('%Y年%m月%d日 %H:%M')}</p>")
        html.append("</div>")
        html.append("</body>")
        html.append("</html>")

        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(html))


# ========== 入口 ==========
if __name__ == "__main__":
    init_db()
    root = tk.Tk()
    app = FamilyTreeApp(root)
    root.mainloop()
