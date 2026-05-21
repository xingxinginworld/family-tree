# -*- coding: utf-8 -*-
"""成员添加/编辑表单模块"""
import tkinter as tk
from tkinter import messagebox, filedialog, ttk
import os
from PIL import Image, ImageTk

from .models import save_member, get_member_by_id, get_all_members


def open_member_dialog(app, member_id=None):
    """打开添加/编辑成员对话框"""
    is_edit = member_id is not None
    member = app.member_map.get(member_id) if is_edit else None

    win = tk.Toplevel(app.root)
    win.title("编辑成员" if is_edit else "添加成员")
    win.geometry("550x720")
    win.transient(app.root)
    win.grab_set()

    # 变量
    name_var     = tk.StringVar(value=member.name if member else "")
    gender_var   = tk.StringVar(value=member.gender if member else "男")
    birth_var    = tk.StringVar(value=member.birth_date if member else "")
    death_var    = tk.StringVar(value=member.death_date if member else "")
    bio_var      = tk.StringVar(value=member.bio if member else "")
    father_var   = tk.StringVar(value=str(member.father_id) if member and member.father_id else "")
    mother_var   = tk.StringVar(value=str(member.mother_id) if member and member.mother_id else "")
    photo_var    = tk.StringVar(value=member.photo_path if member else "")

    form = tk.Frame(win, padx=20, pady=10)
    form.pack(fill=tk.BOTH, expand=True)

    row = 0

    def label(text):
        return tk.Label(form, text=text, font=("微软雅黑", 10), anchor="e", width=12)

    def entry(var, r, width=25):
        e = tk.Entry(form, textvariable=var, font=("微软雅黑", 10), width=width)
        e.grid(row=r, column=1, sticky="w", pady=5)
        return e

    def row_end():
        nonlocal row; row += 1

    # 姓名
    label("姓名 *").grid(row=row, column=0, sticky="e", pady=5); entry(name_var, row); row_end()

    # 性别
    label("性别").grid(row=row, column=0, sticky="e", pady=5)
    gframe = tk.Frame(form)
    gframe.grid(row=row, column=1, sticky="w", pady=5)
    tk.Radiobutton(gframe, text="男", variable=gender_var, value="男",
                   font=("微软雅黑", 10)).pack(side=tk.LEFT, padx=5)
    tk.Radiobutton(gframe, text="女", variable=gender_var, value="女",
                   font=("微软雅黑", 10)).pack(side=tk.LEFT, padx=5)
    row_end()

    # 出生日期
    label("出生日期").grid(row=row, column=0, sticky="e", pady=5); entry(birth_var, row); row_end()

    # 逝世日期
    label("逝世日期").grid(row=row, column=0, sticky="e", pady=5); entry(death_var, row); row_end()

    # 配偶1
    label("配偶").grid(row=row, column=0, sticky="e", pady=5)
    sp1_combo = ttk.Combobox(form, font=("微软雅黑", 10), width=23)
    sp1_vals = ["（无配偶）"] + [
        f"{m.id}. {m.name}（{m.gender or '?'}，第{(m.generation or 1)}代）"
        for m in app.members if m.id != member_id
    ]
    sp1_combo["values"] = sp1_vals
    if member and member.spouse1_id and member.spouse1_id in app.member_map:
        sp1_obj = app.member_map[member.spouse1_id]
        sp1_combo.set(f"{member.spouse1_id}. {sp1_obj.name}（{sp1_obj.gender or '?'}，第{(sp1_obj.generation or 1)}代）")
    sp1_combo.grid(row=row, column=1, sticky="w", pady=5)
    row_end()

    # 配偶2
    label("配偶2").grid(row=row, column=0, sticky="e", pady=5)
    sp2_combo = ttk.Combobox(form, font=("微软雅黑", 10), width=23)
    sp2_vals = ["（无配偶）"] + [
        f"{m.id}. {m.name}（{m.gender or '?'}，第{(m.generation or 1)}代）"
        for m in app.members if m.id != member_id
    ]
    sp2_combo["values"] = sp2_vals
    if member and member.spouse2_id and member.spouse2_id in app.member_map:
        sp2_obj = app.member_map[member.spouse2_id]
        sp2_combo.set(f"{member.spouse2_id}. {sp2_obj.name}（{sp2_obj.gender or '?'}，第{(sp2_obj.generation or 1)}代）")
    sp2_combo.grid(row=row, column=1, sticky="w", pady=5)
    row_end()

    # 父亲
    label("父亲").grid(row=row, column=0, sticky="e", pady=5)
    fa_combo = ttk.Combobox(form, font=("微软雅黑", 10), width=23)
    fa_vals = [""] + [f"{m.id}. {m.name}" for m in app.members
                       if m.id != member_id and m.gender == "男"]
    fa_combo["values"] = fa_vals
    if member and member.father_id and member.father_id in app.member_map:
        fa_combo.set(f"{member.father_id}. {app.member_map[member.father_id].name}")
    fa_combo.grid(row=row, column=1, sticky="w", pady=5)
    row_end()

    # 母亲
    label("母亲").grid(row=row, column=0, sticky="e", pady=5)
    mo_combo = ttk.Combobox(form, font=("微软雅黑", 10), width=23)
    mo_vals = [""] + [f"{m.id}. {m.name}" for m in app.members
                       if m.id != member_id and m.gender == "女"]
    mo_combo["values"] = mo_vals
    if member and member.mother_id and member.mother_id in app.member_map:
        mo_combo.set(f"{member.mother_id}. {app.member_map[member.mother_id].name}")
    mo_combo.grid(row=row, column=1, sticky="w", pady=5)
    row_end()

    # 照片
    tk.Label(form, text="寸照", font=("微软雅黑", 10), anchor="e", width=12)\
        .grid(row=row, column=0, sticky="e", pady=5)
    photo_main = tk.Frame(form)
    photo_main.grid(row=row, column=1, sticky="w", pady=5)

    upload_row = tk.Frame(photo_main)
    upload_row.pack(side=tk.LEFT)
    tk.Entry(upload_row, textvariable=photo_var, font=("微软雅黑", 10),
             width=20).pack(side=tk.LEFT)
    tk.Button(upload_row, text="选择图片", font=("微软雅黑", 9),
              command=lambda: select_photo_internal(photo_var, preview_label),
              cursor="hand2").pack(side=tk.LEFT, padx=5)

    preview_label = tk.Label(photo_main, text="", font=("微软雅黑", 8),
                             bg="#eee", width=12, height=6,
                             anchor="center", justify="center")
    preview_label.pack(side=tk.LEFT, padx=(10, 0))

    # 已有照片则显示预览
    if member and member.photo_path and os.path.exists(member.photo_path):
        try:
            img = Image.open(member.photo_path)
            img = img.resize((80, 100), Image.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            preview_label.config(image=photo, text="")
            preview_label.image = photo
        except:
            pass
    row_end()

    # 简介
    tk.Label(form, text="个人简介", font=("微软雅黑", 10), anchor="ne", width=12)\
        .grid(row=row, column=0, sticky="ne", pady=5)
    bio_text = tk.Text(form, font=("微软雅黑", 10), width=30, height=4)
    bio_text.grid(row=row, column=1, sticky="w", pady=5)
    if member:
        bio_text.insert("1.0", member.bio or "")
    row_end()

    # ── 保存 ──────────────────────────────────────────────

    def save():
        name = name_var.get().strip()
        if not name:
            messagebox.showwarning("提示", "姓名为必填项")
            return

        def parse_id(combo):
            v = combo.get().strip()
            if not v or v in ("（无配偶）",):
                return None
            try:
                return int(v.split(".")[0])
            except:
                return None

        data = {
            "name":       name,
            "gender":     gender_var.get(),
            "birth_date": birth_var.get().strip() or None,
            "death_date": death_var.get().strip() or None,
            "father_id":  parse_id(fa_combo),
            "mother_id":  parse_id(mo_combo),
            "spouse1_id": parse_id(sp1_combo),
            "spouse2_id": parse_id(sp2_combo),
            "bio":        bio_text.get("1.0", tk.END).strip(),
            "photo_path": photo_var.get().strip() or None,
            "extra_photos": member.extra_photos if member else [],
        }

        new_id = save_member(data, member_id)

        # 双向配偶关联
        saved_id = new_id if not is_edit else member_id
        for sp_id in [s for s in [data["spouse1_id"], data["spouse2_id"]] if s]:
            _set_spouse(sp_id, saved_id)

        win.destroy()
        app.load_data()
        messagebox.showinfo("成功", "保存成功！")

    def _set_spouse(target_id, self_id):
        from .db import get_conn
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

    btn_frame = tk.Frame(win)
    btn_frame.pack(pady=15)
    tk.Button(btn_frame, text="保存", font=("微软雅黑", 10), command=save,
              bg="#27ae60", fg="white", cursor="hand2", width=12).pack(side=tk.LEFT, padx=5)
    tk.Button(btn_frame, text="取消", font=("微软雅黑", 10), command=win.destroy,
              width=12).pack(side=tk.LEFT, padx=5)


def select_photo_internal(var, preview_label):
    """选择照片并更新预览"""
    select_photo(None, var, preview_label)


def select_photo(app, var, preview_label=None):
    """选择照片文件（兼容 app 为 None 的调用方式）"""
    path = filedialog.askopenfilename(
        title="选择照片",
        filetypes=[("图片文件", "*.jpg *.jpeg *.png *.bmp"), ("所有文件", "*.*")]
    )
    if not path:
        return
    var.set(path)
    if preview_label:
        _update_preview(preview_label, path)


def _update_preview(label, path):
    """更新照片预览"""
    try:
        if path and os.path.exists(path):
            img = Image.open(path)
            img = img.resize((80, 100), Image.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            label.config(image=photo, text="")
            label.image = photo
        else:
            label.config(image="", text="[无照片]")
            label.image = None
    except Exception:
        label.config(image="", text="[照片加载失败]")
        label.image = None
