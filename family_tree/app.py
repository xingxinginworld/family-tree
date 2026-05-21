# -*- coding: utf-8 -*-
"""主程序模块 - FamilyTreeApp 核心类"""
import tkinter as tk
from tkinter import messagebox
import os
from PIL import Image, ImageTk

from .models import (
    get_all_members, get_member_by_id,
    save_member, delete_member, calc_generations,
    get_all_wall_photos, delete_wall_photo,


)
from . import ui_member, ui_tree, ui_photo_wall, ui_stories, io_csv, io_print
from . import fill_placeholder_images as fpi


class FamilyTreeApp:
    def __init__(self, root):
        self.root = root
        self.root.title("家谱制作工具 v2.6f")
        self.root.geometry("1100x750")

        self.members = []
        self.member_map = {}
        self.tree_canvas = None
        self.canvas_items = {}
        self.node_width = 120
        self.node_height = 60
        self.level_height = 200
        self.scale = 1.0
        self.tree_photo_images = {}
        self.wall_photo_images = {}

        self.expanded_ids = set()    # 已展开的节点ID（单击切换）
        self.node_positions = {}     # 家谱树节点坐标 {id: (x, y)}
        self.setup_ui()
        self.load_data()

    # ── 基础数据 ────────────────────────────────────────────

    def load_data(self):
        calc_generations()  # 确保所有成员代次正确
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
            mid = filtered[idx].id
            self.locate_on_tree(mid)
            self.show_member_detail(mid)

    def confirm_delete(self, member_id, win):
        if messagebox.askyesno("确认删除", "确定删除该成员吗？"):
            delete_member(member_id)
            win.destroy()
            self.load_data()

    def batch_delete_dialog(self):
        """批量删除成员（先提醒导出，再选择要删除的成员）"""
        if not self.members:
            messagebox.showinfo("提示", "当前没有成员可删除")
            return

        # 第一步：提醒先导出
        if not messagebox.askyesno("⚠️ 重要提醒",
            "批量删除不可撤销！\n\n建议先「导出CSV」备份数据，确认已备份后再继续。\n\n是否已备份？"):
            return

        # 第二步：打开多选删除对话框
        win = tk.Toplevel(self.root)
        win.title("批量删除成员")
        win.geometry("420x500")
        win.transient(self.root)
        win.grab_set()

        tk.Label(win, text="勾选要删除的成员：", font=("微软雅黑", 11, "bold"),
                 fg="#e74c3c").pack(anchor="w", padx=18, pady=(14, 4))
        tk.Label(win, text="取消勾选则保留", font=("微软雅黑", 9),
                 fg="#888").pack(anchor="w", padx=18, pady=(0, 8))

        # 带复选框的列表
        list_frame = tk.Frame(win)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=18)
        sb = tk.Scrollbar(list_frame)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        canvas = tk.Canvas(list_frame, borderwidth=0,
                           highlightthickness=0, yscrollcommand=sb.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.config(command=canvas.yview)

        inner = tk.Frame(canvas)
        canvas.create_window((0, 0), window=inner, anchor="nw")

        # 变量映射：checkbox_var -> member_id
        checkboxes = {}  # member_id -> (tk.BooleanVar, Label文本)
        for m in self.members:
            var = tk.BooleanVar(value=False)
            gen_txt = f"第{m.generation}代" if m.generation else ""
            icon = "♂" if m.gender == "男" else "♀" if m.gender == "女" else ""
            row = tk.Frame(inner)
            row.pack(fill=tk.X, pady=2)
            tk.Checkbutton(row, variable=var).pack(side=tk.LEFT)
            tk.Label(row, text=f"{icon} {m.name}（{gen_txt}）",
                     font=("微软雅黑", 10)).pack(side=tk.LEFT, padx=4)
            checkboxes[m.id] = var

        # 全选/取消全选
        sel_frame = tk.Frame(win)
        sel_frame.pack(fill=tk.X, padx=18, pady=(6, 0))
        def toggle_all(select_all):
            for var in checkboxes.values():
                var.set(select_all)
        tk.Button(sel_frame, text="全选", font=("微软雅黑", 9),
                  command=lambda: toggle_all(True)).pack(side=tk.LEFT, padx=2)
        tk.Button(sel_frame, text="取消全选", font=("微软雅黑", 9),
                  command=lambda: toggle_all(False)).pack(side=tk.LEFT, padx=2)

        # 滚动区域更新
        inner.update_idletasks()
        canvas.config(scrollregion=canvas.bbox("all"))
        inner.bind("<Configure>",
                   lambda e: canvas.config(scrollregion=canvas.bbox("all")))

        # 删除按钮 + 结果回调
        result_label = tk.Label(win, text="", font=("微软雅黑", 9), fg="#888")
        result_label.pack()

        def do_delete():
            to_delete = [mid for mid, var in checkboxes.items() if var.get()]
            if not to_delete:
                messagebox.showwarning("提示", "请先勾选要删除的成员")
                return
            if not messagebox.askyesno("确认删除",
                f"确定要删除已勾选的 {len(to_delete)} 位成员吗？\n\n此操作不可撤销！"):
                return
            for mid in to_delete:
                delete_member(mid)
            self.load_data()
            result_label.config(text=f"已删除 {len(to_delete)} 位成员", fg="#e74c3c")
            win.after(1500, win.destroy)

        btn_frame = tk.Frame(win)
        btn_frame.pack(pady=12)
        tk.Button(btn_frame, text="执行删除", font=("微软雅黑", 11),
                  command=do_delete, bg="#e74c3c", fg="white",
                  cursor="hand2", padx=16, pady=4).pack(side=tk.LEFT)

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
        info_row("世代", f"第{member.generation}代" if member.generation is not None else "未计算")

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

    def locate_on_tree(self, member_id):
        """在左侧选中成员时，展开祖先路径并居中显示到该成员节点"""
        if member_id not in self.member_map:
            return

        # 追溯祖先链（father_id/mother_id 向上到顶点）
        ancestors = set()
        mid = member_id
        while mid is not None:
            ancestors.add(mid)
            m = self.member_map.get(mid)
            if not m:
                break
            # 沿 father_id 向上追溯（优先取父亲线）
            parent = m.father_id or m.mother_id
            if parent is None:
                break
            mid = parent

        # 展开祖先链中所有有子女的节点
        for aid in ancestors:
            m = self.member_map.get(aid)
            if m:
                # 检查是否有子女
                for c in self.members:
                    if c.father_id == aid or c.mother_id == aid:
                        self.expanded_ids.add(aid)
                        break

        # 重绘家谱树
        self.draw_tree()

        # 居中滚动到目标节点（等一帧让 Canvas 完成布局）
        def _scroll_to_node():
            pos = self.node_positions.get(member_id)
            if pos is None or not self.tree_canvas.winfo_exists():
                return
            cx, cy = pos
            cw = self.tree_canvas.winfo_width()
            ch = self.tree_canvas.winfo_height()

            # 获取 scrollregion
            bbox = self.tree_canvas.bbox("all")
            if not bbox:
                return
            sx1, sy1, sx2, sy2 = bbox
            sw = sx2 - sx1
            sh = sy2 - sy1
            if sw <= 0 or sh <= 0:
                return

            # 计算居中位置
            fx = (cx - cw / 2 - sx1) / sw
            fy = (cy - ch / 2 - sy1) / sh
            fx = max(0, min(1, fx))
            fy = max(0, min(1, fy))
            self.tree_canvas.xview_moveto(fx)
            self.tree_canvas.yview_moveto(fy)

        self.root.after(50, _scroll_to_node)

    def collapse_all(self):
        """一键收起所有展开的节点"""
        self.expanded_ids.clear()
        self.draw_tree()

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

    def backup_all_data(self):
        io_csv.backup_all(self)

    def restore_all_data(self):
        io_csv.restore_all(self)

    # ── 打印 ───────────────────────────────────────────────

    def show_print_preview(self):
        io_print.show_print_dialog(self)

    def show_placeholder_filler(self):
        """打开CSV图片占位填充工具（独立对话框）"""
        win = tk.Toplevel(self.root)
        fpi.PlaceholderApp(win)

    # ── UI 布局 ─────────────────────────────────────────────

    def setup_ui(self):
        # ── 顶栏：左侧标题 + 右侧工具按钮 ───────────────────
        top = tk.Frame(self.root, height=48, bg="#2c3e50")
        top.pack(fill=tk.X)
        tk.Label(top, text="家谱制作工具", font=("微软雅黑", 15, "bold"),
                 fg="white", bg="#2c3e50").pack(side=tk.LEFT, padx=15, pady=10)

        # 右侧快捷按钮（最常用）
        for text, cmd, bg in [
            ("故事",  self.show_stories,         "#16a085"),
            ("照片",  self.show_photo_wall,      "#9b59b6"),
            ("+ 成员", self.add_member_dialog,   "#27ae60"),
        ]:
            tk.Button(top, text=text, command=cmd,
                      font=("微软雅黑", 9), bg=bg, fg="white",
                      cursor="hand2", relief=tk.FLAT,
                      padx=8, pady=4).pack(side=tk.RIGHT, padx=3, pady=8)

        # "更多 ▼" 下拉菜单
        self._more_btn = tk.Button(
            top, text="更多 ▼", font=("微软雅黑", 9),
            bg="#7f8c8d", fg="white", cursor="hand2",
            relief=tk.FLAT, padx=8, pady=4)
        self._more_btn.pack(side=tk.RIGHT, padx=3, pady=8)

        self._more_menu = tk.Menu(self.root, tearoff=0, font=("微软雅黑", 10))
        self._more_menu.add_command(label="导入模板", command=self.download_template)
        self._more_menu.add_command(label="导入成员", command=self.import_members_csv)
        self._more_menu.add_command(label="导出成员", command=self.export_members_csv)
        self._more_menu.add_separator()
        self._more_menu.add_command(label="导入故事", command=self.import_stories)
        self._more_menu.add_command(label="导出故事", command=self.export_stories)
        self._more_menu.add_separator()
        self._more_menu.add_command(label="打印预览", command=self.show_print_preview)
        self._more_menu.add_separator()
        self._more_menu.add_command(label="一键备份", command=self.backup_all_data)
        self._more_menu.add_command(label="一键恢复", command=self.restore_all_data)
        self._more_menu.add_separator()
        self._more_menu.add_command(label="占位填充", command=self.show_placeholder_filler)
        self._more_btn.config(command=lambda: self._more_menu.post(
            self._more_btn.winfo_rootx(),
            self._more_btn.winfo_rooty() + self._more_btn.winfo_height()))

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

        # ── 批量操作按钮 ─────────────────────────────────────
        batch_frame = tk.Frame(left, bg="#ecf0f1")
        batch_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        tk.Button(batch_frame, text="批量删除成员", font=("微软雅黑", 9),
                  command=self.batch_delete_dialog,
                  bg="#e74c3c", fg="white", cursor="hand2",
                  relief=tk.FLAT, padx=8, pady=4).pack(fill=tk.X)

        # ── 右侧：家谱树 ──────────────────────────────────────
        self.right_frame = tk.Frame(self.root, bg="white")
        self.right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        tk.Label(self.right_frame, text="家谱树（点击节点查看详情）",
                 font=("微软雅黑", 11), bg="white").pack(pady=5)

        # ── 工具栏（树操作） ────────────────────────────
        toolbar = tk.Frame(self.right_frame, bg="white")
        toolbar.pack(fill=tk.X, padx=10, pady=(0, 2))

        btn_font = ("微软雅黑", 9)
        btn_kw = dict(font=btn_font, fg="white", cursor="hand2",
                      relief=tk.FLAT, padx=6, pady=2)
        for text, cmd, bg in [
            ("刷新",  self.draw_tree,               "#3498db"),
            ("放大",  lambda: self.zoom_tree(1.2),   "#95a5a6"),
            ("缩小",  lambda: self.zoom_tree(0.8),  "#95a5a6"),
            ("收起",  self.collapse_all,            "#e67e22"),
        ]:
            tk.Button(toolbar, text=text, command=cmd,
                      bg=bg, **btn_kw).pack(side=tk.LEFT, padx=2)

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

