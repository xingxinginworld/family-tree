# -*- coding: utf-8 -*-
"""打印预览模块 - 生成适合打印/导出PDF的HTML"""
import os
import base64
import webbrowser
import tempfile
from datetime import datetime
from tkinter import Toplevel, Label, Button, messagebox
import tkinter.ttk as ttk


# ============================================================================
# HTML 模板
# ============================================================================

def _photo_inline(path):
    """将图片转为 base64 内嵌格式"""
    try:
        with open(path, "rb") as f:
            data = base64.b64encode(f.read()).decode()
        ext = path.split(".")[-1].lower()
        mime = "image/jpeg" if ext in ("jpg", "jpeg") else "image/png"
        if mime == "image/png":
            mime = "image/gif" if ext == "gif" else mime
        return f"data:{mime};base64,{data}"
    except:
        return None


def _build_tree_html(member_ids, member_map, all_members):
    """构建树形图 HTML（table 分层布局）"""
    # 按 generation 分组
    gens = {}
    for mid in member_ids:
        m = member_map.get(mid)
        if not m:
            continue
        gen = m.generation if m.generation is not None else 1
        gens.setdefault(gen, []).append(m)

    if not gens:
        return "<p style='text-align:center;color:#999;padding:40px;'>无成员数据</p>"

    lines = []
    for gen in sorted(gens.keys()):
        members = gens[gen]
        families = _spouse_pairs(members, member_map)
        line = "<div class='gen-row'>"
        line += f"<div class='gen-label'>第{gen}代</div>"
        line += "<div class='gen-members'>"
        for group in families:
            if len(group) == 2:
                # 夫妻：虚线框包裹
                line += "<div class='family-box'>"
            for m in group:
                life = ""
                if m.birth_date:
                    life += m.birth_date
                if m.death_date:
                    life += f" ~ {m.death_date}"
                elif life:
                    life += " 在世"

                src = _photo_inline(m.photo_path) if m.photo_path and os.path.exists(m.photo_path) else None
                cls = "node"
                if m.gender == "女":
                    cls += " female"
                elif m.gender == "男":
                    cls += " male"
                if m.death_date:
                    cls += " deceased"

                if src:
                    photo_html = f"<div class='node-photo'><img src='{src}'></div>"
                else:
                    photo_html = "<div class='node-photo node-photo-empty'>○</div>"

                line += f"<div class='{cls}'>{photo_html}<div class='node-name'>{m.name}</div>"
                if life:
                    line += f"<div class='node-life'>{life}</div>"
                line += "</div>"
            if len(group) == 2:
                line += "</div>"
        line += "</div></div>"
        lines.append(line)

    return "\n".join(lines)


def _build_members_html(member_ids, member_map):
    """构建成员列表 HTML"""
    if not member_ids:
        return ""
    members = [member_map[mid] for mid in member_ids if mid in member_map]
    gens = {}
    for m in members:
        gen = m.generation if m.generation is not None else 1
        gens.setdefault(gen, []).append(m)

    lines = []
    for gen in sorted(gens.keys()):
        members = gens[gen]
        families = _spouse_pairs(members, member_map)
        lines.append(f"<h3 class='section-h'>第{gen}代</h3>")
        lines.append("<table class='m-table'><thead><tr>"
                     "<th>姓名</th><th>生卒</th><th>关系</th><th>备注</th></tr></thead><tbody>")
        for group in families:
            is_couple = len(group) == 2
            for i, m in enumerate(group):
                life = f"{m.birth_date or ''} - {m.death_date or '在世'}".strip(" -")
                rel = _rel(m, member_map)
                sp = _spouse(m, member_map)
                bdr = ""
                if is_couple:
                    bdr = " style='border:1.5px dashed #e67e22"
                    if i == 0:
                        bdr += ";border-bottom:none'"
                    else:
                        bdr += ";border-top:none'"
                lines.append(f"<tr{bdr}><td><strong>{m.name}</strong></td>"
                             f"<td>{life}</td><td>{rel}</td><td>{sp}</td></tr>")
        lines.append("</tbody></table>")
    return "\n".join(lines)


def _sort_key(m):
    """排序键：出生日期越早越靠前，无出生日期按姓名"""
    return (m.birth_date or "Z9999", m.name)


def _spouse_pairs(members, member_map):
    """将一代成员分成家庭组（夫妻+单身），按出生日期排序
    
    返回: [[member1, member2], [member3], ...]  每组夫妻或单身
    """
    # 构建配偶快速查询表
    spouse_of = {}
    for m in members:
        for sk in ("spouse1_id", "spouse2_id"):
            sid = getattr(m, sk, None)
            if sid and sid in member_map:
                spouse_of[m.id] = sid

    grouped = set()
    families = []
    for m in members:
        if m.id in grouped:
            continue
        sp_id = spouse_of.get(m.id)
        # 配偶也在本代且还未分组
        if sp_id and sp_id in {mm.id for mm in members} and sp_id not in grouped:
            sp = member_map[sp_id]
            families.append([m, sp])
            grouped.add(m.id)
            grouped.add(sp_id)
        else:
            families.append([m])
            grouped.add(m.id)

    # 每组用最早生日成员排序
    families.sort(key=lambda grp: _sort_key(min(grp, key=_sort_key)))
    return families


def _is_spouse(m1, m2):
    """判断两成员是否为配偶"""
    for sk in ("spouse1_id", "spouse2_id"):
        if getattr(m1, sk, None) == m2.id:
            return True
    return False


def _rel(m, mm):
    if m.father_id and m.father_id in mm:
        fa = mm[m.father_id]
        if m.mother_id and m.mother_id in mm:
            mo = mm[m.mother_id]
            return f"{fa.name}、{mo.name}之{'子' if m.gender == '男' else '女'}"
        return f"{fa.name}之{'子' if m.gender == '男' else '女'}"
    if m.mother_id and m.mother_id in mm:
        mo = mm[m.mother_id]
        return f"{mo.name}之{'子' if m.gender == '男' else '女'}"
    for sk in ("spouse1_id", "spouse2_id"):
        sid = getattr(m, sk, None)
        if sid and sid in mm:
            sp = mm[sid]
            return f"{sp.name}之{'夫' if m.gender == '女' else '妻'}"
    return ""


def _spouse(m, mm):
    parts = []
    for sk in ("spouse1_id", "spouse2_id"):
        sid = getattr(m, sk, None)
        if sid and sid in mm:
            parts.append(mm[sid].name)
    if m.bio:
        parts.append(m.bio)
    return "、".join(parts)


def _build_photo_wall_html(member_ids, member_map, all_members, wall_photos,
                           photo_ids=None, columns=3):
    """构建照片墙 HTML（自动包含关联到 member_ids 中成员的照片）"""
    member_set = set(member_ids)
    photos = []

    # 成员寸照
    for mid in member_ids:
        m = member_map.get(mid)
        if not m:
            continue
        if m.photo_path and os.path.exists(m.photo_path):
            photos.append((m.photo_path, m.name, ""))

    # 照片墙：筛选关联成员在本次打印范围内的照片
    for p in wall_photos:
        if not os.path.exists(p.file_path):
            continue
        p_mids = p.get_member_ids()
        if photo_ids is not None:
            # 兼容旧调用（传入指定 ID 列表）
            if p.id not in photo_ids:
                continue
        else:
            # 自动模式：照片关联的任何成员在本次打印范围内
            if not p_mids or not any(mid in member_set for mid in p_mids):
                continue
        ln = member_map[p.member_id].name if p.member_id and p.member_id in member_map else ""
        photos.append((p.file_path, ln, p.caption or ""))

    if not photos:
        return ""
    lines = []
    lines.append(f"<div class='photo-grid' style='grid-template-columns:repeat({columns},1fr)'>")
    for fp, ln, cap in photos:
        src = _photo_inline(fp)
        if not src:
            continue
        cap_short = (cap[:30] + "…") if cap and len(cap) > 30 else (cap or "")
        lines.append(f"<div class='pw-item'>"
                     f"<div class='pw-img'><img src='{src}'></div>"
                     f"<div class='pw-caption'><strong>{ln}</strong>{cap_short and '<br>' + cap_short}</div>"
                     f"</div>")
    lines.append("</div>")
    return "\n".join(lines)


CSS = """
@page {
    size: A5;
    margin: 8mm 7mm;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
    font-family: 'Microsoft YaHei', 'SimSun', sans-serif;
    font-size: 9px;
    color: #222;
    background: white;
}

/* 封面 */
.cover {
    text-align: center;
    padding: 30px 15px 20px;
    page-break-after: always;
}
.cover h1 {
    font-size: 1.8em;
    letter-spacing: 8px;
    color: #2c3e50;
    margin-bottom: 12px;
}
.cover-sub { font-size: 0.95em; color: #666; margin-bottom: 6px; }
.cover-date { font-size: 0.85em; color: #999; margin-top: 20px; }

/* 分区 */
.section { margin-bottom: 12px; }
.section-h {
    font-size: 0.95em;
    color: #2c3e50;
    border-left: 3px solid #3498db;
    padding-left: 6px;
    margin: 12px 0 6px;
}

/* 家谱树 - 分代表格 */
.gen-row {
    display: flex;
    margin-bottom: 6px;
    min-height: 36px;
}
.gen-label {
    width: 30px;
    font-size: 8px;
    color: #888;
    text-align: right;
    padding-right: 4px;
    flex-shrink: 0;
    padding-top: 4px;
}
.gen-members {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    flex: 1;
    border-left: 1.5px solid #b0c4de;
    padding-left: 5px;
}
.node {
    display: flex;
    align-items: center;
    gap: 3px;
    background: white;
    border: 1px solid #2c3e50;
    border-radius: 3px;
    padding: 2px 4px;
    max-width: 140px;
}
.node-photo {
    width: 22px;
    height: 28px;
    flex-shrink: 0;
    border-radius: 2px;
    overflow: hidden;
    background: #eee;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 12px;
    color: #ccc;
}
.node-photo img { width: 100%; height: 100%; object-fit: cover; }
.node-photo-empty { border: 1px dashed #ccc; }
.node.male { border-color: #3498db; background: #f0f7ff; }
.node.female { border-color: #e91e63; background: #fff0f5; }
.node.deceased { opacity: 0.65; }
.node-name { font-size: 9px; font-weight: bold; }
.node-life { font-size: 7px; color: #777; }
.node-spouse { font-size: 7px; color: #e67e22; }
.family-box {
    display: inline-flex;
    align-items: center;
    gap: 3px;
    border: 1px dashed #e67e22;
    border-radius: 4px;
    padding: 2px 4px;
}
.family-box .node { border: none; padding: 1px; }

/* 连接线（伪元素） */
.gen-members::before {
    content: '';
    display: block;
}

/* 成员表 */
.m-table { width: 100%; border-collapse: collapse; margin-bottom: 8px; font-size: 9px; }
.m-table th {
    background: #34495e;
    color: white;
    padding: 3px 5px;
    text-align: center;
}
.m-table td {
    padding: 2px 5px;
    border-bottom: 1px solid #eee;
    vertical-align: middle;
}
.m-table tbody tr:nth-child(even) td { background: #f9f9f9; }
.m-table td:first-child { text-align: left; font-weight: bold; }

/* 照片墙 */
.photo-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(100px, 1fr));
    gap: 6px;
}
.pw-item {
    background: white;
    border: 1px solid #ddd;
    border-radius: 3px;
    overflow: hidden;
}
.pw-img {
    width: 100%;
    aspect-ratio: 3 / 4;
    overflow: hidden;
    background: #f5f5f5;
}
.pw-img img { width: 100%; height: 100%; object-fit: contain; }
.pw-caption { padding: 3px 5px; font-size: 8px; }

/* 页脚 */
.footer {
    text-align: center;
    font-size: 7px;
    color: #bbb;
    padding: 8px 0 0;
    border-top: 1px solid #eee;
    margin-top: 12px;
}

/* 打印控制 */
@media print {
    .no-print { display: none !important; }
    body { font-size: 8px; }
    .cover { page-break-after: always; }
    .section { page-break-inside: avoid; }
    .gen-members { flex-wrap: wrap; }
    .photo-grid { grid-template-columns: repeat(auto-fill, minmax(80px, 1fr)); }
    .m-table { font-size: 8px; }
}
"""


def generate_print_html(member_ids, member_map, all_members, wall_photos,
                        photo_ids=None, columns=3, include_cover=True):
    """生成打印用 HTML（返回字符串）"""
    today = datetime.now().strftime("%Y年%m月%d日")
    tree_html = _build_tree_html(member_ids, member_map, all_members)
    members_html = _build_members_html(member_ids, member_map)
    photos_html = _build_photo_wall_html(member_ids, member_map, all_members,
                                         wall_photos, photo_ids, columns)

    parts = []
    parts.append("<!DOCTYPE html><html lang='zh-CN'>")
    parts.append("<head><meta charset='UTF-8'>")
    parts.append(f"<title>家谱打印预览</title>")
    parts.append("<style>")
    parts.append(CSS)
    parts.append("</style></head><body>")

    # 封面
    if include_cover:
        parts.append("<div class='cover'>")
        parts.append("<h1>家 谱</h1>")
        parts.append(f"<p class='cover-sub'>共 {len(member_ids)} 位家族成员</p>")
        parts.append(f"<p class='cover-sub'>编制日期：{today}</p>")
        parts.append("</div>")

    # 家谱树
    parts.append("<div class='section'>")
    parts.append("<h2 class='section-h'>世系图</h2>")
    parts.append(tree_html)
    parts.append("</div>")

    # 成员详情
    if members_html:
        parts.append("<div class='section'>")
        parts.append("<h2 class='section-h'>成员详情</h2>")
        parts.append(members_html)
        parts.append("</div>")

    # 照片墙
    if photos_html:
        parts.append("<div class='section'>")
        parts.append("<h2 class='section-h'>照片墙</h2>")
        parts.append(photos_html)
        parts.append("</div>")

    # 页脚
    parts.append("<div class='footer'>")
    parts.append(f"<p>家谱制作工具 v2.6f | 编制于 {today}</p>")
    parts.append("</div>")

    parts.append("</body></html>")
    return "\n".join(parts)


# ============================================================================
# Tkinter 选择对话框
# ============================================================================

def _get_subtree_ids(root_id, member_map, all_members, max_depth=None):
    """获取以 root_id 为根的后代 ID（max_depth=None 表示不限代次）"""
    result = set()
    queue = [(root_id, 0)]  # (id, depth)
    while queue:
        cid, depth = queue.pop(0)
        if cid in result:
            continue
        result.add(cid)

        # 已达最大深度：只加配偶，不加子女
        if max_depth is not None and depth >= max_depth - 1:
            m = member_map.get(cid)
            if m:
                for sk in ("spouse1_id", "spouse2_id"):
                    sp_id = getattr(m, sk, None)
                    if sp_id and sp_id not in result and sp_id in member_map:
                        result.add(sp_id)
            continue

        m = member_map.get(cid)
        if m:
            # 配偶（同深度）
            for sk in ("spouse1_id", "spouse2_id"):
                sp_id = getattr(m, sk, None)
                if sp_id and sp_id not in result and sp_id in member_map:
                    queue.append((sp_id, depth))
            # 子女
            for child in all_members:
                if child.father_id == cid or child.mother_id == cid:
                    if child.id not in result:
                        queue.append((child.id, depth + 1))
    return result


def show_print_dialog(app):
    """弹出成员选择对话框，生成并打开打印预览 HTML"""
    if not app.members:
        messagebox.showwarning("提示", "没有成员数据可打印")
        return

    import tkinter as tk

    top = Toplevel(app.root)
    top.title("打印预览")
    top.geometry("500x580")
    top.transient(app.root)
    top.grab_set()

    # 变量
    sel_var = tk.StringVar(value="all")

    Label(top, text="选择打印范围：", font=("微软雅黑", 12, "bold")).pack(anchor="w", padx=20, pady=(18, 8))

    def on_sel_change():
        v = sel_var.get()
        combo_frame.pack_forget() if v == "all" else combo_frame.pack(fill="x", padx=35, pady=6)

    tk.Radiobutton(top, text="全族成员（全部打印）", variable=sel_var, value="all",
                   command=on_sel_change, font=("微软雅黑", 11)).pack(anchor="w", padx=30)
    tk.Radiobutton(top, text="指定成员及其后代（从以下选择）", variable=sel_var, value="sub",
                   command=on_sel_change, font=("微软雅黑", 11)).pack(anchor="w", padx=30)

    combo_frame = ttk.Frame(top)

    # 搜索框
    search_var = tk.StringVar()
    search_entry = tk.Entry(combo_frame, textvariable=search_var,
                            font=("微软雅黑", 10), width=40)
    search_entry.pack(anchor="w", padx=0, pady=(0, 4))
    search_entry.insert(0, "输入姓名筛选...")
    search_entry.config(fg="#aaa")
    search_entry.bind("<FocusIn>", lambda e: (
        search_entry.delete(0, tk.END), search_entry.config(fg="#000")
    ) if search_entry.get() == "输入姓名筛选..." else None)
    search_entry.bind("<FocusOut>", lambda e: (
        search_entry.delete(0, tk.END), search_entry.insert(0, "输入姓名筛选..."),
        search_entry.config(fg="#aaa")
    ) if not search_entry.get() else None)

    def rebuild_combo(*args):
        keyword = search_var.get().strip()
        filtered = [m for m in app.members
                    if not keyword or keyword.lower() in m.name.lower()
                    or keyword == "输入姓名筛选..."]
        combo_vals = [f"{m.id}. {m.name}（第{(m.generation or 1)}代）" for m in filtered]
        combo["values"] = combo_vals
        if combo_vals:
            combo.current(0)
        else:
            combo.set("")

    search_var.trace("w", rebuild_combo)

    combo = ttk.Combobox(combo_frame, state="readonly", width=42, font=("微软雅黑", 11))
    combo.pack(anchor="w", padx=0, pady=(0, 0))
    rebuild_combo()  # 初始化

    # 后代数量控制
    depth_frame = tk.Frame(combo_frame)
    tk.Label(depth_frame, text="后代数量：", font=("微软雅黑", 10)).pack(side=tk.LEFT)
    depth_var = tk.StringVar(value="不限")
    depth_spin = tk.Spinbox(depth_frame, from_=1, to=20, textvariable=depth_var,
                            width=5, font=("微软雅黑", 10))
    depth_spin.pack(side=tk.LEFT)
    tk.Label(depth_frame, text="代（设为 1 仅本人）", font=("微软雅黑", 8),
             fg="#888").pack(side=tk.LEFT, padx=4)
    depth_frame.pack(anchor="w", padx=0, pady=(6, 0))

    sep = ttk.Separator(top, orient="horizontal")
    sep.pack(fill="x", padx=20, pady=10)

    # ── 照片墙列数设置 ─────────────────────────────────
    cols_frame = tk.Frame(top)
    tk.Label(cols_frame, text="照片墙每行显示：", font=("微软雅黑", 10)).pack(side=tk.LEFT)
    cols_var = tk.StringVar(value="3")
    cols_spin = tk.Spinbox(cols_frame, from_=1, to=6, textvariable=cols_var,
                           width=4, font=("微软雅黑", 10))
    cols_spin.pack(side=tk.LEFT, padx=4)
    tk.Label(cols_frame, text="张", font=("微软雅黑", 10)).pack(side=tk.LEFT)
    cols_frame.pack(anchor="w", padx=20, pady=(6, 4))

    # ── 打印按钮 ────────────────────────────────────────────

    def on_print():
        sel = sel_var.get()
        if sel == "all":
            member_ids = [m.id for m in app.members]
        else:
            try:
                root_id = int(combo.get().split(".")[0])
            except:
                messagebox.showwarning("提示", "请先选择一个起始成员")
                return
            # 代次深度
            dv = depth_var.get()
            try:
                max_depth = int(dv) if dv != "不限" else None
            except:
                max_depth = None
            member_ids = list(_get_subtree_ids(root_id, app.member_map,
                                               app.members, max_depth))

        try:
            columns = int(cols_var.get())
        except:
            columns = 3

        from .models import get_all_wall_photos
        wall_photos = get_all_wall_photos()
        html = generate_print_html(member_ids, app.member_map, app.members,
                                   wall_photos, columns=columns)

        # 保存到临时文件（浏览器打开后立即清理）
        tmp_path = os.path.join(tempfile.gettempdir(), f"family_tree_preview_{id(app)}.html")
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(html if isinstance(html, str) else html.decode("utf-8"))

        try:
            webbrowser.open(f"file:///{tmp_path}")
            messagebox.showinfo("已打开",
                f"已在浏览器中打开打印预览\n\n保存 PDF 方法：\n浏览器 → Ctrl+P → 目标打印机选「另存为PDF」→ 保存")
        except Exception as e:
            messagebox.showerror("错误", f"无法打开浏览器：{e}")
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        top.destroy()

    Button(top, text="打开打印预览", command=on_print,
           bg="#3498db", fg="white", font=("微软雅黑", 13), width=18, height=2).pack(pady=8)

    Label(top, text="提示：浏览器中按 Ctrl+P 可另存为 PDF",
          font=("微软雅黑", 9), fg="#999").pack(pady=(0, 12))
