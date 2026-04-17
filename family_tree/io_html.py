# -*- coding: utf-8 -*-
"""HTML 导出模块"""
import os
import base64
from datetime import datetime
from tkinter import filedialog, messagebox

from .models import get_all_wall_photos, get_all_stories


CSS = """
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
    .gen-table { width: 100%; border-collapse: collapse; margin-bottom: 30px; background: white; box-shadow: 0 1px 4px rgba(0,0,0,0.08); }
    .gen-table th { background: #34495e; color: white; padding: 10px 12px; text-align: center; font-size: 0.95em; }
    .gen-table td { padding: 8px 12px; text-align: center; font-size: 0.9em; border-bottom: 1px solid #ecf0f1; vertical-align: middle; }
    .gen-table tbody tr:nth-child(even) { background: #f8f9fa; }
    .gen-table tbody tr:hover { background: #eaf2ff; }
    .gen-table td:first-child { font-weight: bold; color: #2c3e50; }
    .gen-table td:last-child { text-align: left; color: #555; }
    .story-card { background: white; border-radius: 8px; padding: 20px; margin-bottom: 20px; box-shadow: 0 2px 6px rgba(0,0,0,0.08); }
    .story-card h3 { color: #2c3e50; margin-bottom: 6px; }
    .story-card .story-meta { color: #999; font-size: 0.85em; margin-bottom: 10px; }
    .story-card .story-content { color: #555; line-height: 1.8; }
    .story-card img { max-width: 100%; border-radius: 6px; margin: 10px 0; }
    .footer { text-align: center; padding: 40px; color: #999; font-size: 0.9em; }
    @media print { body { background: white; } .member-card { break-inside: avoid; } }
"""


def export_html(app):
    """导出家谱为 HTML"""
    if not app.members:
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
        _generate(app, path)
        messagebox.showinfo("成功", f"已导出至：\n{path}\n请用浏览器打开并打印为PDF")
    except Exception as e:
        messagebox.showerror("错误", f"导出失败：{e}")


def _generate(app, path):
    """生成 HTML 文件"""
    generations = {}
    for m in app.members:
        gen = m.generation if m.generation is not None else 0
        generations.setdefault(gen, []).append(m)

    html = []
    html.append("<!DOCTYPE html><html lang='zh-CN'>")
    html.append("<head><meta charset='UTF-8'>")
    html.append(f"<title>家谱 - {datetime.now().strftime('%Y年%m月%d日')}</title>")
    html.append("<style>")
    html.append(CSS)
    html.append("</style></head><body>")

    # 封面
    html.append("<div class='cover'>")
    html.append("<h1>家谱</h1>")
    html.append(f"<p>共 {len(app.members)} 位家族成员</p>")
    html.append(f"<p class='date'>编制日期：{datetime.now().strftime('%Y年%m月%d日')}</p>")
    html.append("</div>")

    # 世系图
    html.append("<div class='section'>")
    html.append("<h2 class='section-title'>世系图</h2>")
    html.append("<div class='tree-container'><table class='tree-table'>")
    for gen in sorted(generations.keys()):
        html.append("<tr>")
        for m in generations[gen]:
            pt = _photo_tag(m.photo_path)
            gc = "male" if m.gender == "男" else ("female" if m.gender == "女" else "")
            if m.death_date:
                gc += " deceased"
            bi = f"{m.birth_date}" if m.birth_date else ""
            di = f" ~ {m.death_date}" if m.death_date else "（在世）"
            html.append(f"<td><div class='member-card {gc}'>{pt}"
                         f"<div class='name'>{m.name}</div>"
                         f"<div class='info'>{bi}{di}</div></div></td>")
        html.append("</tr>")
    html.append("</table></div></div>")

    # 成员详情表（按世代降序）
    html.append("<div class='section'>")
    html.append("<h2 class='section-title'>成员详情</h2>")
    for gen in sorted(generations.keys(), reverse=True):
        members = sorted(generations[gen], key=lambda x: x.name)
        html.append(f"<h3 style='color:#2c3e50;margin:25px 0 10px;'>第{gen + 1}代</h3>")
        html.append("<table class='gen-table'>")
        html.append("<thead><tr><th>姓名</th><th>生卒年份</th><th>代际</th><th>关系</th><th>配偶/备注</th></tr></thead>")
        html.append("<tbody>")
        for m in members:
            life = f"{m.birth_date or ''} - {m.death_date or '在世'}"
            rel = _calc_relation(m, app.member_map)
            sp_note = _calc_spouse_note(m, app.member_map)
            html.append(f"<tr><td><strong>{m.name}</strong></td>"
                        f"<td>{life}</td><td>第{gen+1}代</td><td>{rel}</td><td>{sp_note}</td></tr>")
        html.append("</tbody></table>")
    html.append("</div>")

    # 照片墙
    all_photos = []
    for m in app.members:
        if m.photo_path and os.path.exists(m.photo_path):
            all_photos.append((m.photo_path, m.name, m.bio))
    for p in get_all_wall_photos():
        if os.path.exists(p.file_path):
            ln = app.member_map[p.member_id].name if p.member_id and p.member_id in app.member_map else ""
            all_photos.append((p.file_path, ln, p.caption))

    if all_photos:
        html.append("<div class='section'>")
        html.append("<h2 class='section-title'>照片墙</h2>")
        html.append("<div class='photo-wall'>")
        for fp, ln, cap in all_photos:
            pt = _photo_tag(fp, linked_name=ln, caption=cap)
            if pt:
                html.append(pt)
        html.append("</div></div>")

    # 故事摘要
    stories = get_all_stories()
    if stories:
        html.append("<div class='section'>")
        html.append("<h2 class='section-title'>故事摘要</h2>")
        member_map_local = {m.id: m.name for m in app.members}
        for s in stories:
            member_name = member_map_local.get(s.member_id, "全局记录")
            meta_parts = []
            if s.author:
                meta_parts.append(f"记录人：{s.author}")
            if s.created_at:
                meta_parts.append(f"编制时间：{s.created_at}")
            if member_name != "全局记录":
                meta_parts.append(f"关联成员：{member_name}")
            meta_str = " | ".join(meta_parts)
            img_tag = ""
            if s.image_path and os.path.exists(s.image_path):
                img_tag = _photo_tag(s.image_path, caption="")
            safe_content = s.content.replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")
            html.append(f"<div class='story-card'>"
                        f"<h3>{s.title}</h3>"
                        f"<div class='story-meta'>{meta_str}</div>"
                        f"{img_tag}"
                        f"<div class='story-content'>{safe_content}</div>"
                        f"</div>")
        html.append("</div>")

    html.append("<div class='footer'>")
    html.append(f"<p>家谱制作工具 v1.9.2 | 编制于 {datetime.now().strftime('%Y年%m月%d日 %H:%M')}</p>")
    html.append("</div></body></html>")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(html))


def _photo_tag(path, linked_name="", caption=""):
    try:
        with open(path, "rb") as f:
            data = base64.b64encode(f.read()).decode()
        ext = path.split(".")[-1].lower()
        mime = "image/jpeg" if ext in ("jpg", "jpeg") else "image/png"
        cap_short = (caption[:40] + "...") if caption and len(caption) > 40 else (caption or "")
        return (f"<div class='photo-item'>"
                f"<img src='data:{mime};base64,{data}'>"
                f"<div class='caption'><strong>{linked_name}</strong>"
                f"<small>{cap_short}</small></div></div>")
    except:
        return ""


def _calc_relation(m, mm):
    if m.father_id and m.father_id in mm:
        fa = mm[m.father_id]
        if m.mother_id and m.mother_id in mm:
            mo = mm[m.mother_id]
            return fa.name + "和" + mo.name + ("的儿子" if m.gender == "男" else "的女儿")
        return fa.name + ("的儿子" if m.gender == "男" else "的女儿")
    if m.mother_id and m.mother_id in mm:
        mo = mm[m.mother_id]
        return mo.name + ("的儿子" if m.gender == "男" else "的女儿")
    for sk in ("spouse1_id", "spouse2_id"):
        sid = getattr(m, sk, None)
        if sid and sid in mm:
            sp = mm[sid]
            return sp.name + ("的丈夫" if m.gender == "女" else "的妻子")
    return ""


def _calc_spouse_note(m, mm):
    parts = []
    for sk in ("spouse1_id", "spouse2_id"):
        sid = getattr(m, sk, None)
        if sid and sid in mm:
            parts.append(mm[sid].name + "；")
    if m.bio:
        parts.append(m.bio)
    return "；".join(parts) if parts else ""
