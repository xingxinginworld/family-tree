# -*- coding: utf-8 -*-
"""故事摘要模块"""
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk, filedialog
from datetime import datetime
import os

from .models import get_all_stories, get_story_by_id, save_story, delete_story


def open_stories_window(app):
    """打开故事摘要管理窗口"""
    win = tk.Toplevel(app.root)
    win.title("故事摘要")
    win.geometry("780x600")
    win.transient(app.root)

    # ── 顶部工具栏 ─────────────────────────────────────────
    toolbar = tk.Frame(win, padx=10, pady=7, bg="#34495e")
    toolbar.pack(fill=tk.X)

    tk.Label(toolbar, text="📖 故事摘要", font=("微软雅黑", 11, "bold"),
             bg="#34495e", fg="white").pack(side=tk.LEFT)

    # 编辑按钮（选中了才可用）
    def _make_edit_cmd():
        def cmd():
            if current_story_id[0] is None:
                messagebox.showwarning("提示", "请先在左侧选择一个故事")
                return
            _open_editor(win, app, current_story_id[0])
        return cmd

    edit_btn = tk.Button(toolbar, text="✎  编辑", font=("微软雅黑", 9),
                          command=_make_edit_cmd(),
                          bg="#3498db", fg="white", cursor="hand2",
                          relief=tk.FLAT, padx=10, pady=3)

    def _make_del_cmd():
        def cmd():
            if current_story_id[0] is None:
                messagebox.showwarning("提示", "请先在左侧选择一个故事")
                return
            if messagebox.askyesno("确认删除", "确定删除该故事？此操作不可恢复。"):
                delete_story(current_story_id[0])
                refresh_list()
                clear_preview()
                current_story_id[0] = None
        return cmd

    del_btn = tk.Button(toolbar, text="✕  删除", font=("微软雅黑", 9),
                         command=_make_del_cmd(),
                         bg="#e74c3c", fg="white", cursor="hand2",
                         relief=tk.FLAT, padx=10, pady=3)

    edit_btn.pack(side=tk.RIGHT, padx=3)
    del_btn.pack(side=tk.RIGHT, padx=3)
    tk.Button(toolbar, text="+ 添加故事", font=("微软雅黑", 9, "bold"),
              command=lambda: _open_editor(win, app, None),
              bg="#27ae60", fg="white", cursor="hand2",
              relief=tk.FLAT, padx=10, pady=3).pack(side=tk.RIGHT, padx=3)

    tk.Frame(win, height=2, bg="#bdc3c7").pack(fill=tk.X)

    # ── 主体：左侧列表 + 右侧预览 ───────────────────────────
    paned = tk.PanedWindow(win, orient=tk.HORIZONTAL, sashpad=2, sashwidth=4, bg="#bdc3c7")
    paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    # 左侧列表
    left_frame = tk.Frame(paned, width=230)
    paned.add(left_frame, width=230)

    list_frame = tk.Frame(left_frame)
    list_frame.pack(fill=tk.BOTH, expand=True, padx=5)
    scroll = tk.Scrollbar(list_frame)
    scroll.pack(side=tk.RIGHT, fill=tk.Y)
    story_listbox = tk.Listbox(list_frame, font=("微软雅黑", 10),
                               yscrollcommand=scroll.set,
                               selectbackground="#3498db",
                               selectforeground="white",
                               activestyle="none")
    story_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scroll.config(command=story_listbox.yview)

    # 右侧预览区
    right_frame = tk.Frame(paned)
    paned.add(right_frame)

    preview_top = tk.Frame(right_frame)
    preview_top.pack(fill=tk.BOTH, expand=True)

    # 标题
    title_var = tk.StringVar(value="（请从左侧选择一个故事查看详情）")
    tk.Label(preview_top, textvariable=title_var,
             font=("微软雅黑", 14, "bold"), anchor="w",
             fg="#2c3e50").pack(fill=tk.X, padx=12, pady=(12, 4))

    # 元信息行
    meta_frame = tk.Frame(preview_top)
    meta_frame.pack(fill=tk.X, padx=12, pady=2)
    tk.Label(meta_frame, text="记录人：", font=("微软雅黑", 9), fg="#999").pack(side=tk.LEFT)
    author_var = tk.StringVar(value="—")
    tk.Label(meta_frame, textvariable=author_var, font=("微软雅黑", 9), fg="#555").pack(side=tk.LEFT)
    tk.Label(meta_frame, text="    编制时间：", font=("微软雅黑", 9), fg="#999").pack(side=tk.LEFT)
    date_var = tk.StringVar(value="—")
    tk.Label(meta_frame, textvariable=date_var, font=("微软雅黑", 9), fg="#555").pack(side=tk.LEFT)
    tk.Label(meta_frame, text="    关联成员：", font=("微软雅黑", 9), fg="#999").pack(side=tk.LEFT)
    member_var = tk.StringVar(value="—")
    tk.Label(meta_frame, textvariable=member_var, font=("微软雅黑", 9), fg="#555").pack(side=tk.LEFT)

    tk.Frame(preview_top, height=1, bg="#ddd").pack(fill=tk.X, padx=12, pady=(6, 4))

    # 图片预览
    img_container = tk.Frame(preview_top, bg="#f0f0f0")
    img_container.pack(fill=tk.X, padx=12, pady=(2, 4))
    img_ref = [None]

    def _clear_img():
        for w in img_container.pack_slaves():
            w.destroy()
        img_ref[0] = None

    # 内容区
    content_text = scrolledtext.ScrolledText(preview_top, font=("微软雅黑", 10),
                                              wrap=tk.WORD, state=tk.DISABLED,
                                              bg="#fafafa", relief=tk.FLAT, borderwidth=0)
    content_text.pack(fill=tk.BOTH, expand=True, padx=12, pady=(2, 5))

    current_story_id = [None]

    # ── 函数 ───────────────────────────────────────────────

    def clear_preview():
        title_var.set("（请从左侧选择一个故事查看详情）")
        author_var.set("—")
        date_var.set("—")
        member_var.set("—")
        content_text.config(state=tk.NORMAL)
        content_text.delete("1.0", tk.END)
        content_text.config(state=tk.DISABLED)
        _clear_img()

    def refresh_list():
        story_listbox.delete(0, tk.END)
        stories = get_all_stories()
        member_map = {m.id: m.name for m in app.members}
        story_listbox.stories_data = []
        for s in stories:
            member_name = member_map.get(s.member_id, "全局")
            story_listbox.insert(tk.END, f"{s.title}  [{member_name}]")
            story_listbox.stories_data.append(s)
        if not stories:
            story_listbox.insert(tk.END, "（暂无故事，点击上方「添加故事」创建）")
            story_listbox.stories_data = []

    def show_story(story_id):
        story = get_story_by_id(story_id)
        if not story:
            return
        current_story_id[0] = story.id
        member_map = {m.id: m.name for m in app.members}
        member_name = member_map.get(story.member_id, "（全局，无关联成员）")
        title_var.set(story.title)
        author_var.set(story.author or "—")
        date_var.set(story.created_at or "—")
        member_var.set(member_name)
        content_text.config(state=tk.NORMAL)
        content_text.delete("1.0", tk.END)
        content_text.insert("1.0", story.content or "")
        content_text.config(state=tk.DISABLED)
        _clear_img()
        if story.image_path and os.path.exists(story.image_path):
            try:
                from PIL import Image, ImageTk
                img = Image.open(story.image_path)
                img.thumbnail((720, 380), Image.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                lbl = tk.Label(img_container, image=photo, bg="#f0f0f0")
                lbl.image = photo
                lbl.pack()
                img_ref[0] = lbl
            except Exception:
                tk.Label(img_container, text=f"[图片：{os.path.basename(story.image_path)}]",
                         font=("微软雅黑", 9), fg="#999", bg="#f0f0f0").pack(anchor="w")
        elif story.image_path:
            tk.Label(img_container, text=f"[图片不存在]", font=("微软雅黑", 9), fg="#c00",
                     bg="#f0f0f0").pack(anchor="w")

    def on_select(event):
        sel = story_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        data = getattr(story_listbox, 'stories_data', [])
        if idx < len(data):
            show_story(data[idx].id)

    story_listbox.bind("<<ListboxSelect>>", on_select)

    # ── 编辑对话框 ──────────────────────────────────────────

    def _open_editor(parent_win, parent_app, story_id):
        story = get_story_by_id(story_id) if story_id else None

        editor = tk.Toplevel(parent_win)
        editor.title("新建故事" if story is None else "编辑故事")
        editor.geometry("520x580")
        editor.transient(parent_win)
        editor.grab_set()

        # 内容足够时允许滚动
        canvas = tk.Canvas(editor, borderwidth=0, bg=editor.cget("bg"))
        scrollbar = ttk.Scrollbar(editor, orient="vertical", command=canvas.yview)
        scroll_frame = tk.Frame(canvas, padx=18, pady=10)

        scroll_frame.bind("<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        f = scroll_frame

        # 标题
        tk.Label(f, text="标题 *", font=("微软雅黑", 10), anchor="e",
                 width=10, fg="#555").grid(row=0, column=0, sticky="e", pady=5)
        title_e = tk.Entry(f, font=("微软雅黑", 11), width=38)
        title_e.grid(row=0, column=1, sticky="ew", pady=5)
        if story:
            title_e.insert(0, story.title)

        # 记录人
        tk.Label(f, text="记录人", font=("微软雅黑", 10), anchor="e",
                 width=10, fg="#555").grid(row=1, column=0, sticky="e", pady=5)
        author_e = tk.Entry(f, font=("微软雅黑", 10), width=38)
        author_e.grid(row=1, column=1, sticky="ew", pady=5)
        if story:
            author_e.insert(0, story.author or "")

        # 关联成员
        tk.Label(f, text="关联成员", font=("微软雅黑", 10), anchor="e",
                 width=10, fg="#555").grid(row=2, column=0, sticky="e", pady=5)
        member_map_local = {m.id: m.name for m in parent_app.members}
        member_combo = ttk.Combobox(f, font=("微软雅黑", 10), width=36)
        member_vals = ["（全局 - 无关联成员）"] + [
            f"{mid}. {mname}" for mid, mname in member_map_local.items()
        ]
        member_combo["values"] = member_vals
        member_combo.grid(row=2, column=1, sticky="ew", pady=5)
        if story and story.member_id:
            member_combo.set(f"{story.member_id}. {member_map_local.get(story.member_id, '')}")
        else:
            member_combo.set("（全局 - 无关联成员）")

        # 编制时间
        tk.Label(f, text="编制时间", font=("微软雅黑", 10), anchor="e",
                 width=10, fg="#555").grid(row=3, column=0, sticky="e", pady=5)
        date_e = tk.Entry(f, font=("微软雅黑", 10), width=38)
        date_e.grid(row=3, column=1, sticky="ew", pady=5)
        date_e.insert(0, story.created_at if story else datetime.now().strftime("%Y-%m-%d"))

        # 配图
        tk.Label(f, text="配图", font=("微软雅黑", 10), anchor="e",
                 width=10, fg="#555").grid(row=4, column=0, sticky="ne", pady=5)
        img_frame = tk.Frame(f)
        img_frame.grid(row=4, column=1, sticky="w", pady=5)
        img_path_var = tk.StringVar(value=story.image_path if story and story.image_path else "")
        preview_lbl = tk.Label(img_frame, text="", anchor="w", bg="#f0f0f0",
                               font=("微软雅黑", 9), fg="#999")

        def _show_preview(path):
            if path and os.path.exists(path):
                try:
                    from PIL import Image, ImageTk
                    im = Image.open(path)
                    im.thumbnail((200, 140), Image.LANCZOS)
                    ph = ImageTk.PhotoImage(im)
                    preview_lbl.configure(image=ph, text="")
                    preview_lbl.image = ph
                except Exception:
                    preview_lbl.configure(image="", text=f"[图片：{os.path.basename(path)}]")
            else:
                preview_lbl.configure(image="", text="未选择图片")

        _show_preview(img_path_var.get())
        preview_lbl.pack(pady=(0, 4))

        def _select_img():
            path = filedialog.askopenfilename(
                title="选择配图",
                filetypes=[("图片文件", "*.jpg *.jpeg *.png *.gif *.bmp *.webp"), ("所有文件", "*.*")]
            )
            if path:
                img_path_var.set(path)
                _show_preview(path)

        tk.Button(img_frame, text="选择图片", font=("微软雅黑", 9),
                  command=_select_img, cursor="hand2", relief=tk.FLAT,
                  bg="#95a5a6", fg="white").pack(side=tk.LEFT, padx=(0, 4))
        tk.Button(img_frame, text="移除", font=("微软雅黑", 9),
                  command=lambda: (img_path_var.set(""), preview_lbl.configure(image="", text="未选择图片"),
                                   setattr(preview_lbl, 'image', None)),
                  cursor="hand2", relief=tk.FLAT, bg="#bdc3c7").pack(side=tk.LEFT)

        # 内容
        tk.Label(f, text="内容 *", font=("微软雅黑", 10), anchor="ne",
                 width=10, fg="#555").grid(row=5, column=0, sticky="ne", pady=5)
        content_te = scrolledtext.ScrolledText(f, font=("微软雅黑", 10),
                                               width=38, height=14, wrap=tk.WORD)
        content_te.grid(row=5, column=1, sticky="nsew", pady=5)
        if story:
            content_te.insert("1.0", story.content or "")

        f.columnconfigure(1, weight=1)
        f.rowconfigure(5, weight=1)

        # 按钮行（在对话框最底部，始终可见）
        btn_f = tk.Frame(editor, pady=8)
        btn_f.pack(fill=tk.X)
        tk.Button(btn_f, text="保存", font=("微软雅黑", 10), width=12,
                  command=lambda: _do_save(),
                  bg="#27ae60", fg="white", cursor="hand2",
                  relief=tk.FLAT, pady=4).pack(side=tk.LEFT, padx=(18, 6))
        tk.Button(btn_f, text="取消", font=("微软雅黑", 10), width=12,
                  command=editor.destroy,
                  relief=tk.FLAT, pady=4).pack(side=tk.LEFT, padx=6)

        def _do_save():
            title = title_e.get().strip()
            content = content_te.get("1.0", tk.END).strip()
            if not title:
                messagebox.showwarning("提示", "标题为必填项")
                return
            if not content:
                messagebox.showwarning("提示", "内容不能为空")
                return
            author = author_e.get().strip() or None
            created = date_e.get().strip() or datetime.now().strftime("%Y-%m-%d")
            img_path = img_path_var.get().strip() or None
            member_sel = member_combo.get().strip()
            if member_sel.startswith("（全局"):
                member_id = None
            else:
                try:
                    member_id = int(member_sel.split(".")[0])
                except Exception:
                    member_id = None

            save_story({
                "title": title,
                "content": content,
                "author": author,
                "created_at": created,
                "member_id": member_id,
                "image_path": img_path,
            }, story_id)

            editor.destroy()
            refresh_list()
            if story_id:
                show_story(story_id)
            messagebox.showinfo("成功", "保存成功！")

    refresh_list()
