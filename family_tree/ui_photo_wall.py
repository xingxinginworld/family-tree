# -*- coding: utf-8 -*-
"""照片墙模块（编号排序 + 说明编辑）"""
import tkinter as tk
import os
import json
import shutil
import json
from tkinter import messagebox, filedialog, ttk
from datetime import datetime
from PIL import Image, ImageTk

from .config import PHOTO_DIR
from .models import get_all_wall_photos, delete_wall_photo, save_photo_order, get_all_members


# ── 窗口入口 ─────────────────────────────────────────────────────────

def open_photo_wall(app):
    """打开照片墙窗口"""
    win = tk.Toplevel(app.root)
    win.title("照片墙")
    win.geometry("900x680")
    win.transient(app.root)

    # ── 工具栏 ──────────────────────────────────────────
    top_bar = tk.Frame(win, bg="#f0f0f0")
    top_bar.pack(fill=tk.X, padx=10, pady=8)

    tk.Button(top_bar, text="上传照片（多选）", font=("微软雅黑", 10),
              command=lambda: _upload_photo(app, win),
              bg="#27ae60", fg="white", cursor="hand2").pack(side=tk.LEFT, padx=3)

    tk.Button(top_bar, text="刷新", font=("微软雅黑", 10),
              command=lambda: _render_list(app, win),
              bg="#3498db", fg="white", cursor="hand2").pack(side=tk.LEFT, padx=3)

    tk.Button(top_bar, text="按编号排序", font=("微软雅黑", 10),
              command=lambda: _sort_by_number(app, win),
              bg="#9b59b6", fg="white", cursor="hand2").pack(side=tk.LEFT, padx=3)

    tk.Button(top_bar, text="全选", font=("微软雅黑", 10),
              command=lambda: _toggle_all_photos(app, win, True),
              bg="#2c3e50", fg="white", cursor="hand2",
              width=5).pack(side=tk.LEFT, padx=3)

    tk.Button(top_bar, text="取消全选", font=("微软雅黑", 10),
              command=lambda: _toggle_all_photos(app, win, False),
              bg="#95a5a6", fg="white", cursor="hand2",
              width=7).pack(side=tk.LEFT, padx=3)

    tk.Button(top_bar, text="批量删除", font=("微软雅黑", 10),
              command=lambda: _batch_delete_photos(app, win),
              bg="#e74c3c", fg="white", cursor="hand2").pack(side=tk.LEFT, padx=3)

    tk.Button(top_bar, text="导出顺序", font=("微软雅黑", 10),
              command=lambda: _export_order(app),
              bg="#16a085", fg="white", cursor="hand2").pack(side=tk.RIGHT, padx=3)

    tk.Button(top_bar, text="导入顺序", font=("微软雅黑", 10),
              command=lambda: _import_order(app, win),
              bg="#16a085", fg="white", cursor="hand2").pack(side=tk.RIGHT, padx=3)

    tk.Label(top_bar, text="💡 支持多选上传，每张照片单独编辑；点「编辑」修编号，点「按编号排序」",
             font=("微软雅黑", 9), fg="#888", bg="#f0f0f0").pack(side=tk.LEFT, padx=20)

    # ── 主画布 ──────────────────────────────────────────
    canvas = tk.Canvas(win, bg="#f0f0f0", highlightthickness=0)
    scrollbar = tk.Scrollbar(win, orient=tk.VERTICAL, command=canvas.yview)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    canvas.config(yscrollcommand=scrollbar.set)

    inner = tk.Frame(canvas, bg="#f0f0f0")
    canvas.create_window((0, 0), window=inner, anchor="nw")

    win._wall_inner = inner
    win._wall_canvas = canvas

    canvas.bind_all("<MouseWheel>",
                    lambda e: canvas.yview_scroll(-1 * (e.delta // 120), tk.UNITS))

    app.wall_photo_images.clear()
    _render_list(app, win)

    win.protocol("WM_DELETE_WINDOW", win.destroy)


# ── 列表渲染 ─────────────────────────────────────────────────────────

def _render_list(app, win):
    """渲染照片列表（每张照片一行）"""
    inner = getattr(win, "_wall_inner", None)
    canvas = getattr(win, "_wall_canvas", None)
    if not inner:
        return

    for child in inner.winfo_children():
        child.destroy()

    wall_photos = get_all_wall_photos()

    if not wall_photos:
        tk.Label(inner, text="暂无照片，点击上方「上传照片（多选）」添加",
                 font=("微软雅黑", 14), fg="#999", bg="#f0f0f0").pack(pady=60)
    else:
        for photo in wall_photos:
            _make_row(app, inner, win, photo)

    if canvas:
        # 延迟等待子 widget 布局完成后，再更新 scrollregion
        def _update_scroll():
            canvas.update_idletasks()
            bbox = canvas.bbox(tk.ALL)
            if bbox:
                canvas.configure(scrollregion=bbox)
            else:
                # fallback：手动计算 inner 高度
                inner.update_idletasks()
                w = canvas.winfo_width()
                h = inner.winfo_reqheight()
                canvas.configure(scrollregion=(0, 0, w, h))

        canvas.after(100, _update_scroll)


# ── 每行照片 ─────────────────────────────────────────────────────────

def _make_row(app, inner, win, photo):
    """构建一行照片（编号 + 缩略图 + 说明 + 操作按钮）"""
    row = tk.Frame(inner, bg="white", bd=1, relief=tk.RAISED)
    row.pack(fill=tk.X, padx=10, pady=4)

    # ── 勾选框（用于批量删除）─────────────────────────
    cb_vars = getattr(win, "_photo_cb_vars", None)
    if cb_vars is None:
        cb_vars = {}
        win._photo_cb_vars = cb_vars
    cb_var = tk.BooleanVar(value=False)
    cb_vars[photo.id] = cb_var
    tk.Checkbutton(row, variable=cb_var, bg="white",
                   cursor="hand2").pack(side=tk.LEFT, padx=(4, 2))

    # ── 编号（只读）─────────────────────────────────────
    num_lbl = tk.Label(row, text=f"#{photo.sort_order or ''}",
                       font=("Consolas", 12, "bold"), width=5,
                       fg="#9b59b6", bg="white", anchor="center")
    num_lbl.pack(side=tk.LEFT, padx=(6, 4), pady=6)

    # ── 缩略图 ──────────────────────────────────────────
    thumb_frame = tk.Frame(row, width=80, height=60, bg="#eee")
    thumb_frame.pack(side=tk.LEFT, padx=4, pady=6)
    thumb_frame.pack_propagate(False)

    def _load_thumb():
        if not os.path.exists(photo.file_path):
            tk.Label(thumb_frame, text="❌\n找不到文件",
                     font=("微软雅黑", 8), fg="#c00", bg="#eee").pack()
            return
        try:
            img = Image.open(photo.file_path)
            img.thumbnail((75, 57), Image.LANCZOS)
            photo_img = ImageTk.PhotoImage(img)
            app.wall_photo_images[photo.id] = photo_img
            lbl = tk.Label(thumb_frame, image=photo_img, bg="#eee", cursor="hand2")
            lbl.image = photo_img
            lbl.pack()
            lbl.bind("<Button-1>", lambda e: _view_photo(photo))
        except Exception as e:
            tk.Label(thumb_frame, text=f"❌\n加载失败",
                     font=("微软雅黑", 8), fg="#c00", bg="#eee").pack()

    row.after(10, _load_thumb)

    # ── 说明文字 ────────────────────────────────────────
    info_frame = tk.Frame(row, bg="white")
    info_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=6, pady=6)

    caption = photo.caption or ""
    display = caption[:60] + ("..." if len(caption) > 60 else "")

    member_name = ""
    if photo.member_id:
        members = get_all_members()
        m = next((m for m in members if m.id == photo.member_id), None)
        if m:
            member_name = f"（{m.name}）"

    status_text = f"{display}{member_name}" if display else f"{member_name}" if member_name else "（无说明）"

    lbl = tk.Label(info_frame, text=status_text,
                   font=("微软雅黑", 10), fg="#555" if caption else "#aaa",
                   bg="white", anchor="w", justify=tk.LEFT)
    lbl.pack(fill=tk.X)

    # ── 操作按钮 ────────────────────────────────────────
    btn_frame = tk.Frame(row, bg="white")
    btn_frame.pack(side=tk.RIGHT, padx=6, pady=6)

    tk.Button(btn_frame, text="编辑", font=("微软雅黑", 9),
              command=lambda: _edit_caption(app, win, photo),
              bg="#3498db", fg="white", cursor="hand2",
              width=5).pack(side=tk.TOP, pady=1)

    tk.Button(btn_frame, text="删除", font=("微软雅黑", 9),
              command=lambda: _delete_photo(app, win, photo),
              bg="#e74c3c", fg="white", cursor="hand2",
              width=5).pack(side=tk.TOP, pady=1)


def _view_photo(photo):
    """在新窗口查看大图"""
    if not os.path.exists(photo.file_path):
        messagebox.showwarning("提示", "找不到图片文件")
        return
    top = tk.Toplevel()
    top.title(os.path.basename(photo.file_path))
    try:
        img = Image.open(photo.file_path)
        w, h = img.size
        max_w, max_h = 900, 700
        if w > max_w or h > max_h:
            ratio = min(max_w / w, max_h / h)
            w, h = int(w * ratio), int(h * ratio)
        photo_img = ImageTk.PhotoImage(Image.open(photo.file_path).resize((w, h), Image.LANCZOS))
        lbl = tk.Label(top, image=photo_img)
        lbl.image = photo_img
        lbl.pack()
    except Exception as e:
        tk.Label(top, text=f"加载失败：{e}", font=("微软雅黑", 12)).pack()


# ── 批量删除 ─────────────────────────────────────────────────────────

def _toggle_all_photos(app, win, select_all):
    """全选或取消全选所有照片"""
    cb_vars = getattr(win, "_photo_cb_vars", {})
    for var in cb_vars.values():
        var.set(select_all)


def _batch_delete_photos(app, win):
    """批量删除照片（先提醒备份，再删勾选的）"""
    cb_vars = getattr(win, "_photo_cb_vars", {})
    selected = [pid for pid, var in cb_vars.items() if var.get()]
    if not selected:
        messagebox.showwarning("提示", "请先勾选要删除的照片")
        return

    # 提醒备份
    if not messagebox.askyesno("⚠️ 重要提醒",
        "批量删除不可撤销！\n\n建议先「备份」数据，确认已备份后再继续。\n\n是否已备份？"):
        return

    # 确认删除
    if not messagebox.askyesno("确认删除",
        f"确定要删除已勾选的 {len(selected)} 张照片吗？\n\n此操作不可撤销！"):
        return

    # 执行
    for pid in selected:
        delete_wall_photo(pid)

    _render_list(app, win)
    messagebox.showinfo("完成", f"已删除 {len(selected)} 张照片")


# ── 排序 ─────────────────────────────────────────────────────────────

def _sort_by_number(app, win):
    """按编号（sort_order）升序排列照片（不改变编号，只重排显示顺序）"""
    wall_photos = get_all_wall_photos()
    if not wall_photos:
        messagebox.showwarning("提示", "照片墙中没有照片")
        return

    # 按编号升序，同编号按 ID 排序（保证唯一顺序）
    sorted_photos = sorted(wall_photos, key=lambda p: (p.sort_order or 0, p.id))

    # 立即刷新显示（数据库 sort_order 保持不变）
    _render_list(app, win)
    messagebox.showinfo("完成", f"已按编号排序（编号未变）")


# ── 导出 / 导入 ────────────────────────────────────────────────────

def _export_order(app):
    """导出照片顺序到 JSON"""
    from .models import export_photo_order
    order = export_photo_order()
    if not order:
        messagebox.showwarning("提示", "照片墙中没有照片可导出")
        return

    path = filedialog.asksaveasfilename(
        title="保存照片顺序", defaultextension=".json",
        filetypes=[("JSON文件", "*.json")], initialfile="照片墙顺序.json"
    )
    if not path:
        return

    data = {"version": 1, "type": "photo_wall_order", "order": order}
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        messagebox.showinfo("成功", f"已导出 {len(order)} 条顺序记录")
    except Exception as e:
        messagebox.showerror("错误", f"导出失败：{e}")


def _import_order(app, win):
    """从 JSON 导入照片顺序"""
    path = filedialog.askopenfilename(
        title="选择照片顺序文件",
        filetypes=[("JSON文件", "*.json"), ("所有文件", "*.*")]
    )
    if not path:
        return

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        messagebox.showerror("错误", f"文件读取失败：{e}")
        return

    order_dict = data.get("order", {})
    if not order_dict:
        messagebox.showwarning("提示", "文件中没有找到顺序数据")
        return

    from .models import import_photo_order
    count = import_photo_order(order_dict)
    messagebox.showinfo("成功", f"已导入 {count} 条顺序记录")
    _render_list(app, win)


# ── 上传 / 删除 / 编辑说明 ──────────────────────────────────────────

def _upload_photo(app, win):
    """上传照片（支持多选，无需逐张确认，自动编号接在末尾）"""
    paths = filedialog.askopenfilenames(
        title="选择照片（可多选）",
        filetypes=[("图片文件", "*.jpg *.jpeg *.png *.bmp *.gif"), ("所有文件", "*.*")]
    )
    if not paths:
        return

    os.makedirs(PHOTO_DIR, exist_ok=True)

    # 查已有最大编号，作为本批的起始值
    from .models import get_all_wall_photos
    existing = get_all_wall_photos()
    max_order = max((p.sort_order or 0) for p in existing) if existing else 0

    from .db import get_conn
    conn = get_conn()
    added = 0

    for i, path in enumerate(paths):
        ext = os.path.splitext(path)[1].lower()
        # 多张时加序号区分
        if len(paths) > 1:
            filename = f"wall_{datetime.now().strftime('%Y%m%d%H%M%S')}_{i+1:02d}{ext}"
        else:
            filename = f"wall_{datetime.now().strftime('%Y%m%d%H%M%S')}{ext}"
        dest_path = os.path.join(PHOTO_DIR, filename)

        try:
            shutil.copy2(path, dest_path)
        except Exception as e:
            messagebox.showerror("错误", f"复制文件失败：{e}")
            continue

        # 默认说明 = 文件名（不含扩展名）
        default_caption = os.path.splitext(os.path.basename(path))[0]
        # 自动编号：接在已有最大编号之后
        sort_val = max_order + i + 1

        conn.execute(
            "INSERT INTO photo_wall (file_path, caption, sort_order) VALUES (?, ?, ?)",
            (dest_path, default_caption, sort_val)
        )
        added += 1

    conn.commit()
    conn.close()

    if added > 0:
        messagebox.showinfo("完成", f"已添加 {added} 张照片")
    _render_list(app, win)


def _delete_photo(app, win, photo):
    """删除照片"""
    if messagebox.askyesno("确认", f"确定要删除「{photo.caption or '这张照片'}」吗？"):
        delete_wall_photo(photo.id)
        # 删除文件（如果还在 photos 目录）
        if os.path.exists(photo.file_path) and "photos" in photo.file_path:
            try:
                os.remove(photo.file_path)
            except:
                pass
        _render_list(app, win)


def _edit_caption(app, win, photo, dest_path=None, initial_caption=""):
    """编辑照片说明（支持新建和已有照片）"""
    # 获取已有照片信息
    existing = photo

    # ── 对话框 ────────────────────────────────────────────
    edit_win = tk.Toplevel(app.root)
    edit_win.title("编辑照片" if existing else "上传照片")
    edit_win.geometry("460x360")
    edit_win.transient(app.root)
    edit_win.grab_set()

    # 顶部固定按钮区
    header = tk.Frame(edit_win, bg="#ecf0f1")
    header.pack(fill=tk.X, side=tk.TOP)
    header.pack_propagate(False)
    header.configure(height=50)

    btn_frame = tk.Frame(header, bg="#ecf0f1")
    btn_frame.pack(pady=8)

    def do_save():
        # 获取多选的成员 ID
        sel_indices = member_list.curselection()
        linked_ids = []
        for idx in sel_indices:
            txt = member_list.get(idx)
            try:
                linked_ids.append(int(txt.split(".")[0]))
            except:
                pass
        linked_id = linked_ids[0] if linked_ids else None
        member_ids_json = json.dumps(linked_ids)

        caption_val = caption_var.get().strip()
        try:
            sort_val = int(num_var.get().strip())
        except:
            sort_val = 1

        from .db import get_conn
        conn = get_conn()

        if existing:
            conn.execute(
                "UPDATE photo_wall SET sort_order=?, caption=?, member_id=?, member_ids=? WHERE id=?",
                (sort_val, caption_val, linked_id, member_ids_json, existing.id)
            )
        else:
            # 新建：dest_path 已在外部复制好，用用户输入的编号
            conn.execute(
                "INSERT INTO photo_wall (file_path, caption, member_id, member_ids, sort_order) "
                "VALUES (?, ?, ?, ?, ?)",
                (dest_path, caption_val, linked_id, member_ids_json, sort_val)
            )
        conn.commit()
        conn.close()

        edit_win.destroy()
        _render_list(app, win)

    tk.Button(btn_frame, text="保存", font=("微软雅黑", 11),
              command=do_save, bg="#27ae60", fg="white",
              cursor="hand2", width=8).pack(side=tk.LEFT, padx=6)

    tk.Button(btn_frame, text="取消", font=("微软雅黑", 11),
              command=edit_win.destroy, bg="#95a5a6", fg="white",
              cursor="hand2", width=8).pack(side=tk.LEFT, padx=6)

    # ── 表单区 ────────────────────────────────────────────
    form = tk.Frame(edit_win, bg="white")
    form.pack(fill=tk.BOTH, expand=True, padx=16, pady=10)

    # 第0行：编号（左）+ 预览图（右，已有照片）
    tk.Label(form, text="编号：", font=("微软雅黑", 10),
             bg="white").grid(row=0, column=0, sticky="nw", pady=8)
    num_var = tk.StringVar(value=str(existing.sort_order if existing else ""))
    tk.Entry(form, textvariable=num_var,
             font=("Consolas", 12, "bold"), width=10).grid(
        row=0, column=1, sticky="w", pady=8)

    if existing and os.path.exists(existing.file_path):
        try:
            img = Image.open(existing.file_path)
            img.thumbnail((130, 100), Image.LANCZOS)
            prev = ImageTk.PhotoImage(img)
            prev_lbl = tk.Label(form, image=prev, bg="white")
            prev_lbl.image = prev
            prev_lbl.grid(row=0, column=2, rowspan=3, sticky="ne", padx=(10, 0), pady=5)
        except:
            pass

    # 第1行：说明文字
    tk.Label(form, text="照片说明：", font=("微软雅黑", 10),
             bg="white").grid(row=1, column=0, sticky="nw", pady=8)
    caption_var = tk.StringVar(value=initial_caption if initial_caption else (existing.caption if existing else ""))
    tk.Entry(form, textvariable=caption_var,
             font=("微软雅黑", 11), width=30).grid(
        row=1, column=1, sticky="ew", pady=8)

    # 第2行：关联成员（多选）
    tk.Label(form, text="关联成员：", font=("微软雅黑", 10),
             bg="white").grid(row=2, column=0, sticky="nw", pady=8)
    member_frame = tk.Frame(form, bg="white")
    member_frame.grid(row=2, column=1, sticky="w", pady=4)

    tk.Label(member_frame, text="Ctrl+点击多选", font=("微软雅黑", 8),
             fg="#888", bg="white").pack(anchor="w")

    list_sb = tk.Scrollbar(member_frame, orient=tk.VERTICAL)
    member_list = tk.Listbox(member_frame, selectmode=tk.MULTIPLE,
                              font=("微软雅黑", 9), height=5, width=35,
                              yscrollcommand=list_sb.set, exportselection=False)
    list_sb.pack(side=tk.RIGHT, fill=tk.Y)
    member_list.pack(side=tk.LEFT, fill=tk.X)
    list_sb.config(command=member_list.yview)

    members = get_all_members()
    existing_mids = existing.get_member_ids() if existing else []
    for idx, m in enumerate(members):
        member_list.insert(tk.END, f"{m.id}. {m.name}")
        if m.id in existing_mids:
            member_list.selection_set(idx)

    form.columnconfigure(1, weight=1)
