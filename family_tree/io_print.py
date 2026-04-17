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
        gen = m.generation if m.generation is not None else 0
        gens.setdefault(gen, []).append(m)

    if not gens:
        return "<p style='text-align:center;color:#999;padding:40px;'>无成员数据</p>"

    lines = []
    max_gen = max(gens.keys())
    for gen in sorted(gens.keys(), reverse=True):
        members = sorted(gens[gen], key=lambda x: x.name)
        line = "<div class='gen-row'>"
        line += f"<div class='gen-label'>第{gen + 1}代</div>"
        line += "<div class='gen-members'>"
        for m in members:
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
        gen = m.generation if m.generation is not None else 0
        gens.setdefault(gen, []).append(m)

    lines = []
    for gen in sorted(gens.keys(), reverse=True):
        ms = sorted(gens[gen], key=lambda x: x.name)
        lines.append(f"<h3 class='section-h'>第{gen + 1}代</h3>")
        lines.append("<table class='m-table'><thead><tr>"
                     "<th>姓名</th><th>生卒</th><th>关系</th><th>配偶/备注</th></tr></thead><tbody>")
        for m in ms:
            life = f"{m.birth_date or ''} - {m.death_date or '在世'}".strip(" -")
            rel = _rel(m, member_map)
            sp = _spouse(m, member_map)
            lines.append(f"<tr><td><strong>{m.name}</strong></td>"
                         f"<td>{life}</td><td>{rel}</td><td>{sp}</td></tr>")
        lines.append("</tbody></table>")
    return "\n".join(lines)


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


def _build_photo_wall_html(member_ids, member_map, all_members, wall_photos):
    """构建照片墙 HTML"""
    photos = []
    for mid in member_ids:
        m = member_map.get(mid)
        if not m:
            continue
        if m.photo_path and os.path.exists(m.photo_path):
            photos.append((m.photo_path, m.name, ""))
    for p in wall_photos:
        if os.path.exists(p.file_path):
            ln = member_map[p.member_id].name if p.member_id and p.member_id in member_map else ""
            photos.append((p.file_path, ln, p.caption or ""))

    if not photos:
        return ""
    lines = []
    lines.append("<div class='photo-grid'>")
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
    size: A4 portrait;
    margin: 15mm 12mm;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
    font-family: 'Microsoft YaHei', 'SimSun', sans-serif;
    font-size: 12px;
    color: #222;
    background: white;
}

/* 封面 */
.cover {
    text-align: center;
    padding: 60px 20px 40px;
    page-break-after: always;
}
.cover h1 {
    font-size: 2.4em;
    letter-spacing: 10px;
    color: #2c3e50;
    margin-bottom: 16px;
}
.cover-sub { font-size: 1.1em; color: #666; margin-bottom: 8px; }
.cover-date { font-size: 0.95em; color: #999; margin-top: 30px; }

/* 分区 */
.section { margin-bottom: 20px; }
.section-h {
    font-size: 1.1em;
    color: #2c3e50;
    border-left: 4px solid #3498db;
    padding-left: 8px;
    margin: 16px 0 8px;
}

/* 家谱树 - 分代表格 */
.gen-row {
    display: flex;
    align-items: center;
    margin-bottom: 12px;
    min-height: 60px;
}
.gen-label {
    width: 50px;
    font-size: 11px;
    color: #888;
    text-align: right;
    padding-right: 8px;
    flex-shrink: 0;
}
.gen-members {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    flex: 1;
    border-left: 2px solid #b0c4de;
    padding-left: 10px;
}
.node {
    display: flex;
    align-items: center;
    gap: 6px;
    background: white;
    border: 1.5px solid #2c3e50;
    border-radius: 4px;
    padding: 5px 8px;
    min-width: 110px;
    max-width: 150px;
}
.node-photo {
    width: 36px;
    height: 44px;
    flex-shrink: 0;
    border-radius: 2px;
    overflow: hidden;
    background: #eee;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 18px;
    color: #ccc;
}
.node-photo img { width: 100%; height: 100%; object-fit: cover; }
.node-photo-empty { border: 1px dashed #ccc; }
.node.male { border-color: #3498db; background: #f0f7ff; }
.node.female { border-color: #e91e63; background: #fff0f5; }
.node.deceased { opacity: 0.65; }
.node-name { font-size: 12px; font-weight: bold; }
.node-life { font-size: 9px; color: #777; }

/* 连接线（伪元素） */
.gen-members::before {
    content: '';
    display: block;
}

/* 成员表 */
.m-table { width: 100%; border-collapse: collapse; margin-bottom: 10px; font-size: 11px; }
.m-table th {
    background: #34495e;
    color: white;
    padding: 5px 8px;
    text-align: center;
}
.m-table td {
    padding: 4px 8px;
    border-bottom: 1px solid #eee;
    vertical-align: middle;
}
.m-table tbody tr:nth-child(even) td { background: #f9f9f9; }
.m-table td:first-child { text-align: left; font-weight: bold; }

/* 照片墙 */
.photo-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 8px;
}
.pw-item {
    background: white;
    border: 1px solid #ddd;
    border-radius: 4px;
    overflow: hidden;
}
.pw-img { height: 100px; overflow: hidden; }
.pw-img img { width: 100%; height: 100%; object-fit: cover; }
.pw-caption { padding: 4px 6px; font-size: 10px; }

/* 页脚 */
.footer {
    text-align: center;
    font-size: 9px;
    color: #bbb;
    padding: 10px 0 0;
    border-top: 1px solid #eee;
    margin-top: 16px;
}

/* 打印控制 */
@media print {
    .no-print { display: none !important; }
    body { font-size: 11px; }
    .cover { page-break-after: always; }
    .section { page-break-inside: avoid; }
    .gen-members { flex-wrap: wrap; }
}
"""


def generate_print_html(member_ids, member_map, all_members, wall_photos, include_cover=True):
    """生成打印用 HTML（返回字符串）"""
    today = datetime.now().strftime("%Y年%m月%d日")
    tree_html = _build_tree_html(member_ids, member_map, all_members)
    members_html = _build_members_html(member_ids, member_map)
    photos_html = _build_photo_wall_html(member_ids, member_map, all_members, wall_photos)

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
    parts.append(f"<p>家谱制作工具 v2.5 | 编制于 {today}</p>")
    parts.append("</div>")

    parts.append("</body></html>")
    return "\n".join(parts)


# ============================================================================
# Tkinter 选择对话框
# ============================================================================

def _get_subtree_ids(root_id, member_map, all_members):
    """获取以 root_id 为根的所有后代 ID（BFS）"""
    result = set()
    queue = [root_id]
    while queue:
        cid = queue.pop(0)
        result.add(cid)
        for m in all_members:
            if m.father_id == cid or m.mother_id == cid:
                if m.id not in result:
                    queue.append(m.id)
    return result


def show_print_dialog(app):
    """弹出成员选择对话框，生成并打开打印预览 HTML"""
    if not app.members:
        messagebox.showwarning("提示", "没有成员数据可打印")
        return

    import tkinter as tk

    top = Toplevel(app.root)
    top.title("打印预览")
    top.geometry("480x420")
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
    combo_vals = [f"{m.id}. {m.name}（第{(m.generation or 0)+1}代）" for m in app.members]
    combo = ttk.Combobox(combo_frame, values=combo_vals, state="readonly", width=42, font=("微软雅黑", 11))
    combo.current(0)
    combo.pack(anchor="w", padx=0, pady=(4, 0))

    sep = ttk.Separator(top, orient="horizontal")
    sep.pack(fill="x", padx=20, pady=14)

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
            member_ids = list(_get_subtree_ids(root_id, app.member_map, app.members))

        from .models import get_all_wall_photos
        wall_photos = get_all_wall_photos()
        html = generate_print_html(member_ids, app.member_map, app.members, wall_photos)

        # 保存到临时文件
        tmp = tempfile.NamedTemporaryFile(suffix=".html", delete=False, encoding="utf-8")
        tmp.write(html if isinstance(html, str) else html.decode("utf-8"))
        tmp.close()

        try:
            webbrowser.open(f"file:///{tmp.name}")
            messagebox.showinfo("已打开",
                f"已在浏览器中打开打印预览\n\n保存 PDF 方法：\n浏览器 → Ctrl+P → 目标打印机选「另存为PDF」→ 保存")
        except Exception as e:
            messagebox.showerror("错误", f"无法打开浏览器：{e}")
        top.destroy()

    Button(top, text="打开打印预览", command=on_print,
           bg="#3498db", fg="white", font=("微软雅黑", 13), width=18, height=2).pack(pady=8)

    Label(top, text="提示：浏览器中按 Ctrl+P 可另存为 PDF",
          font=("微软雅黑", 9), fg="#999").pack(pady=(0, 12))
