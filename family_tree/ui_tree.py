# -*- coding: utf-8 -*-
"""家谱树绘制模块"""
import os
from PIL import Image, ImageTk


def draw_tree(app):
    """绘制家谱树"""
    app.tree_canvas.delete("all")
    app.canvas_items.clear()
    app.tree_photo_images.clear()

    if not app.members:
        app.tree_canvas.create_text(400, 300,
                                    text="暂无成员，请添加成员开始",
                                    font=("微软雅黑", 14), fill="#999")
        return

    roots = [m for m in app.members
             if m.father_id is None and m.mother_id is None]

    node_positions = {}
    nw = app.node_width
    nh = app.node_height

    def place_tree(members, x, y, level, used_x):
        spacing = nw + 30
        # children_map: member_id -> [child_id, ...]（存储ID而非对象）
        children_map = {}
        for m in members:
            children_map[m.id] = [c.id for c in app.members
                                  if c.father_id == m.id or c.mother_id == m.id]

        total = len(members)
        if total == 0:
            return x

        start_x = x - spacing * (total - 1) / 2
        for i, m in enumerate(members):
            cx = start_x + i * spacing
            node_positions[m.id] = (cx, y)
            kid_ids = children_map.get(m.id, [])
            if kid_ids:
                start_child_x = cx - (len(kid_ids) - 1) * spacing / 2
                new_y = y + app.level_height
                for j, kid_id in enumerate(kid_ids):
                    child_x = start_child_x + j * spacing
                    px, py = node_positions[m.id]
                    app.tree_canvas.create_line(
                        px, py + nh // 2, child_x, new_y - nh // 2,
                        fill="#555", width=1.5
                    )

        if any(children_map.get(m.id) for m in members):
            child_y = y + app.level_height
            child_ids = [kid_id for m in members for kid_id in children_map.get(m.id, [])]
            child_members = [app.member_map[cid] for cid in child_ids if cid in app.member_map]
            place_tree(child_members, x, child_y, level + 1, used_x)

        return start_x

    for i, root in enumerate(roots):
        start_y = 80 + i * 300
        place_tree([root], 500, start_y, 0, set())

    # 配偶连线
    for m in app.members:
        x, y = node_positions.get(m.id, (0, 0))
        for sp_attr, line_color, lstyle in [
            ("spouse1_id", "#e67e22", (4, 4)),
            ("spouse2_id", "#c0392b", (6, 3)),
        ]:
            sp_id = getattr(m, sp_attr, None)
            if sp_id and sp_id in node_positions and sp_id > m.id:
                sx, sy = node_positions[sp_id]
                app.tree_canvas.create_line(
                    x + nw // 2, y,
                    sx - nw // 2, sy,
                    fill=line_color, width=1.5, dash=lstyle
                )

    # 渲染节点
    for m_id, (x, y) in node_positions.items():
        m = app.member_map.get(m_id)
        if m:
            _draw_node(app, m, x, y)

    # 居中
    if node_positions:
        xs = [p[0] for p in node_positions.values()]
        ys = [p[1] for p in node_positions.values()]
        max_x, max_y = max(xs), max(ys)
        avg_x, avg_y = sum(xs) / len(xs), sum(ys) / len(ys)
        app.tree_canvas.config(scrollregion=(-50, -50, max_x + 250, max_y + 100))
        app.tree_canvas.xview_moveto(max(0, (avg_x - 400) / max(max_x, 1)))
        app.tree_canvas.yview_moveto(max(0, (avg_y - 300) / max(max_y, 1)))


def _draw_node(app, member, x, y):
    """绘制单个成员节点"""
    nw = app.node_width
    nh = app.node_height

    if member.death_date:
        bg = "#95a5a6"
    elif member.gender == "男":
        bg = "#3498db"
    elif member.gender == "女":
        bg = "#e91e63"
    else:
        bg = "#9b59b6"

    tag = f"node_{member.id}"
    app.tree_canvas.create_rectangle(
        x - nw // 2, y - nh // 2,
        x + nw // 2, y + nh // 2,
        fill=bg, outline="#2c3e50", width=2, tags=tag
    )

    # 1寸照片（36x48px）
    pw, ph = 36, 48
    px, py = x - nw // 2 + 6, y - ph // 2

    if member.photo_path and os.path.exists(member.photo_path):
        try:
            img = Image.open(member.photo_path)
            img = img.resize((pw, ph), Image.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            app.tree_photo_images[member.id] = photo
            app.tree_canvas.create_image(px, py, image=photo, anchor="nw", tags=tag)
        except:
            app.tree_canvas.create_rectangle(px, py, px + pw, py + ph,
                                              fill="#ddd", outline="#aaa", width=1, tags=tag)
    else:
        app.tree_canvas.create_rectangle(px, py, px + pw, py + ph,
                                          fill="#ddd", outline="#aaa", width=1, tags=tag)
        app.tree_canvas.create_text(px + pw // 2, py + ph // 2,
                                    text="○", font=("Arial", 14), fill="#aaa", tags=tag)

    # 文字放右侧
    tx = x + pw // 2 + 10
    app.tree_canvas.create_text(tx, y - 8, text=member.name,
                                font=("微软雅黑", 11, "bold"), fill="white", tags=tag)
    app.tree_canvas.create_text(tx, y + 12,
                                 text=f"第{member.generation + 1}代"
                                      if member.generation is not None else "",
                                 font=("微软雅黑", 8), fill="#eee", tags=tag)

    def on_click(event, mid=member.id):
        app.show_member_detail(mid)

    app.tree_canvas.tag_bind(tag, "<Button-1>", on_click)
    app.canvas_items[member.id] = tag


def zoom_tree(app, factor):
    """缩放家谱树"""
    app.scale *= factor
    app.scale = max(0.3, min(3.0, app.scale))
    app.tree_canvas.scale("all",
                           app.tree_canvas.winfo_width() // 2,
                           app.tree_canvas.winfo_height() // 2,
                           factor, factor)
