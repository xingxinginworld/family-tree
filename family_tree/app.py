# -*- coding: utf-8 -*-
"""主程序模块 - FamilyTreeApp 核心类"""
import tkinter as tk
from tkinter import messagebox
import os
from PIL import Image, ImageTk

from .models import (
    get_all_members, get_member_by_id,
    save_member, delete_member,
    get_all_wall_photos, delete_wall_photo,


)
from . import ui_member, ui_tree, ui_photo_wall, ui_stories, io_csv, io_html, io_print


class FamilyTreeApp:
    def __init__(self, root):
        self.root = root
        self.root.title("家谱制作工具 v2.6")
        self.root.geometry("1100x750")

        self.members = []
        self.member_map = {}
        self.tree_canvas = None
        self.canvas_items = {}
        self.node_width = 120
        self.node_height = 60
        self.level_height = 100
        self.scale = 1.0
        self.tree_photo_images = {}
        self.wall_photo_images = {}

        self.setup_ui()
        self.load_data()

    # ── 基础数据 ────────────────────────────────────────────

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
            icon = "♂" if m.gender == "男" else "♀" if m.gender == "女" else ""
            self.member_listbox.insert(tk.END, f"{icon} {m.name}")

    def filter_members(self):
        self.update_member_list(self.search_var.get())

    def on_member_select(self, event):
        sel = self.member_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        ft = self.search_var.get()
        filtered = [m for m in self.members
                    if not ft or ft.lower() in m.name.lower()]
        if idx < len(filtered):
            self.show_member_detail(filtered[idx].id)

    def confirm_delete(self, member_id, win):
        if messagebox.askyesno("确认删除", "确定删除该成员吗？"):
            delete_member(member_id)
            win.destroy()
            self.load_data()

    # ── 成员详情 ────────────────────────────────────────────

    def show_member_detail(self, member_id):
        member = get_member_by_id(member_id)
        if not member:
            return

        win = tk.Toplevel(self.root)
        win.title(f"成员详情 - {member.name}")
        win.geometry("500x600")
        win.transient(self.root)
        win.grab_set()

        # 照片
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

        # 信息区
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

        if member.father_id and member.father_id in self.member_map:
            info_row("父亲", self.member_map[member.father_id].name)
        if member.mother_id and member.mother_id in self.member_map:
            info_row("母亲", self.member_map[member.mother_id].name)
        if member.spouse1_id and member.spouse1_id in self.member_map:
            info_row("配偶", self.member_map[member.spouse1_id].name)
        if member.spouse2_id and member.spouse2_id in self.member_map:
            info_row("配偶2", self.member_map[member.spouse2_id].name)

        if member.bio:
            tk.Label(info_frame, text="简介：", font=("微软雅黑", 10, "bold"),
                     anchor="w").pack(pady=(10, 2))
            tk.Label(info_frame, text=member.bio, font=("微软雅黑", 9),
                     wraplength=450, justify="left", anchor="w").pack()

        # 按钮
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

    # ── 添加/编辑 ────────────────────────────────────────────

    def add_member_dialog(self):
        ui_member.open_member_dialog(self, member_id=None)

    def edit_member_dialog(self, member_id):
        ui_member.open_member_dialog(self, member_id=member_id)

    # ── 家谱树 ───────────────────────────────────────────────

    def draw_tree(self):
        ui_tree.draw_tree(self)

    def zoom_tree(self, factor):
        ui_tree.zoom_tree(self, factor)

    # ── 照片墙 ───────────────────────────────────────────────

    def show_photo_wall(self):
        ui_photo_wall.open_photo_wall(self)

    # ── 故事摘要 ───────────────────────────────────────────

    def show_stories(self):
        ui_stories.open_stories_window(self)

    def _refresh_photo_wall(self, win):
        ui_photo_wall.refresh_content(self, win)

    def _do_delete_photo(self, photo_id, win):
        if messagebox.askyesno("确认", "确定删除该照片？"):
            delete_wall_photo(photo_id)
            self._refresh_photo_wall(win)

    def upload_wall_photo(self, parent_win):
        ui_photo_wall.upload_photo(self, parent_win)

    def select_photo(self, var, preview_label=None):
        ui_member.select_photo(self, var, preview_label)

    # ── CSV ─────────────────────────────────────────────────

    def download_template(self):
        io_csv.download_template()

    def export_members_csv(self):
        io_csv.export_csv(self)

    def import_members_csv(self):
        io_csv.import_csv(self)

    def export_stories(self):
        io_csv.export_stories(self)

    def import_stories(self):
        io_csv.import_stories(self)

    # ── HTML ────────────────────────────────────────────────

    def export_html(self):
        io_html.export_html(self)

    def show_print_preview(self):
        io_print.show_print_dialog(self)

    # ── UI 布局 ─────────────────────────────────────────────

    def setup_ui(self):
        # ── 顶栏：左侧标题 + 右侧工具按钮 ───────────────────
        top = tk.Frame(self.root, height=48, bg="#2c3e50")
        top.pack(fill=tk.X)
        tk.Label(top, text="家谱制作工具", font=("微软雅黑", 15, "bold"),
                 fg="white", bg="#2c3e50").pack(side=tk.LEFT, padx=15, pady=10)

        # 右侧工具按钮组
        for text, cmd, bg in [
            ("+ 添加成员",  self.add_member_dialog,   "#27ae60"),
            ("照片墙",      self.show_photo_wall,     "#8e44ad"),
            ("故事摘要",    self.show_stories,         "#16a085"),
            ("导出HTML",    self.export_html,          "#e67e22"),
            ("下载模板",    self.download_template,    "#2980b9"),
            ("导出CSV",     self.export_members_csv,   "#2980b9"),
            ("导入CSV",     self.import_members_csv,   "#8e44ad"),
            ("导出故事",    self.export_stories,       "#c0392b"),
            ("导入故事",    self.import_stories,       "#c0392b"),
            ("打印预览",    self.show_print_preview,    "#e74c3c"),
        ]:
            tk.Button(top, text=text, command=cmd,
                      font=("微软雅黑", 9), bg=bg, fg="white",
                      cursor="hand2", relief=tk.FLAT,
                      padx=8, pady=4).pack(side=tk.RIGHT, padx=3, pady=8)

        # ── 左侧栏：搜索 + 成员列表 ──────────────────────────
        left = tk.Frame(self.root, width=250, bg="#ecf0f1")
        left.pack(side=tk.LEFT, fill=tk.Y)
        left.pack_propagate(False)

        tk.Label(left, text="家族成员", font=("微软雅黑", 11, "bold"),
                 bg="#ecf0f1").pack(pady=(12, 5))

        self.search_var = tk.StringVar()
        self.search_var.trace("w", lambda *a: self.filter_members())
        tk.Entry(left, textvariable=self.search_var,
                 font=("微软雅黑", 10)).pack(fill=tk.X, padx=10)

        list_frame = tk.Frame(left, bg="#ecf0f1")
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)
        sb = tk.Scrollbar(list_frame)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.member_listbox = tk.Listbox(list_frame, font=("微软雅黑", 10),
                                         yscrollcommand=sb.set,
                                         selectbackground="#3498db",
                                         selectforeground="white")
        self.member_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.config(command=self.member_listbox.yview)
        self.member_listbox.bind("<<ListboxSelect>>", self.on_member_select)

        # ── 右侧：家谱树 ──────────────────────────────────────
        self.right_frame = tk.Frame(self.root, bg="white")
        self.right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        tk.Label(self.right_frame, text="家谱树（点击节点查看详情）",
                 font=("微软雅黑", 11), bg="white").pack(pady=5)

        toolbar = tk.Frame(self.right_frame, bg="white")
        toolbar.pack(fill=tk.X, padx=10)
        for text, cmd, bg in [
            ("刷新",  self.draw_tree,               "#3498db"),
            ("放大",  lambda: self.zoom_tree(1.2),   "#95a5a6"),
            ("缩小",  lambda: self.zoom_tree(0.8),  "#95a5a6"),
        ]:
            tk.Button(toolbar, text=text, command=cmd, font=("微软雅黑", 9),
                      bg=bg, fg="white", cursor="hand2").pack(side=tk.LEFT, padx=3)

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

