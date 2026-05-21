# -*- coding: utf-8 -*-
"""家谱树绘制模块 — 逐代排布 + 折叠展开"""
import os
from PIL import Image, ImageTk


def draw_tree(app):
    """绘制家谱树（默认只显示始祖，单击展开子代，双击查看详情）"""
    app.tree_canvas.delete("all")
    app.canvas_items.clear()
    app.tree_photo_images.clear()

    if not app.members:
        app.tree_canvas.create_text(400, 300,
                                    text="暂无成员，请添加成员开始",
                                    font=("微软雅黑", 14), fill="#999")
        return

    nw = app.node_width
    nh = app.node_height
    spacing = nw + 30
    level_h = app.level_height

    # Step 1: 计算可见成员
    visible_ids = _calc_visible_ids(app)

    # Step 2: 仅对可见成员分配位置
    gen_groups = {}
    for m in app.members:
        if m.id not in visible_ids:
            continue
        gen = m.generation if m.generation is not None else 1
        gen_groups.setdefault(gen, []).append(m)

    node_positions = {}
    for gen in sorted(gen_groups.keys()):
        members = sorted(gen_groups[gen], key=lambda x: x.id)
        count = len(members)
        if count == 0:
            continue
        start_x = 500 - (count * spacing) / 2 + spacing / 2
        y = 80 + (gen - 1) * level_h
        for i, m in enumerate(members):
            node_positions[m.id] = (start_x + i * spacing, y)

    # Step 3: 画连线（仅可见的父子/配偶对）
    for m in app.members:
        if m.id not in visible_ids or m.id not in node_positions:
            continue
        cx, cy = node_positions[m.id]

        # 父子连线（仅目标也可见时）
        kid_ids = [c.id for c in app.members
                   if (c.father_id == m.id or c.mother_id == m.id)
                   and c.id in visible_ids]
        for kid_id in kid_ids:
            if kid_id in node_positions:
                kx, ky = node_positions[kid_id]
                app.tree_canvas.create_line(
                    cx, cy + nh // 2, kx, ky - nh // 2,
                    fill="#555", width=1.5
                )

        # 配偶连线
        for sp_attr, line_color, lstyle in [
            ("spouse1_id", "#e67e22", (4, 4)),
            ("spouse2_id", "#c0392b", (6, 3)),
        ]:
            sp_id = getattr(m, sp_attr, None)
            if sp_id and sp_id in visible_ids and sp_id in node_positions and sp_id > m.id:
                sx, sy = node_positions[sp_id]
                app.tree_canvas.create_line(
                    cx + nw // 2, cy,
                    sx - nw // 2, sy,
                    fill=line_color, width=1.5, dash=lstyle
                )

    # Step 4: 绘制可见节点
    for m_id, (x, y) in node_positions.items():
        m = app.member_map.get(m_id)
        if m:
            _draw_node(app, m, x, y, visible_ids)

    # Step 5: 滚动区域（仅基于可见节点）
    if node_positions:
        xs = [p[0] for p in node_positions.values()]
        ys = [p[1] for p in node_positions.values()]
        max_x, max_y = max(xs), max(ys)
        min_x = min(xs)
        min_y = min(ys)
        avg_x, avg_y = sum(xs) / len(xs), sum(ys) / len(ys)
        app.tree_canvas.config(scrollregion=(min_x - 100, min_y - 50,
                                              max_x + 200, max_y + 100))
        app.tree_canvas.xview_moveto(max(0, (avg_x - 400) / max(max_x - min_x, 1)))
        app.tree_canvas.yview_moveto(max(0, (avg_y - 300) / max(max_y - min_y, 1)))

    app.node_positions = node_positions


def _calc_visible_ids(app):
    """计算可见成员 ID
    规则：
      - generation=1 的始祖（含始祖的配偶）始终可见
      - 某成员可见且已展开 → 其子女可见
      - 某成员可见 → 其配偶可见
    """
    if not hasattr(app, 'expanded_ids'):
        app.expanded_ids = set()

    # 始基：generation=1 的成员始终可见（始祖+始祖配偶）
    visible = set()
    for m in app.members:
        if m.generation == 1:
            visible.add(m.id)

    # 迭代展开
    changed = True
    while changed:
        changed = False
        for m in app.members:
            if m.id in visible:
                continue

            # 通过父母可见且展开
            if m.father_id is not None and m.father_id in visible and m.father_id in app.expanded_ids:
                visible.add(m.id)
                changed = True
            elif m.mother_id is not None and m.mother_id in visible and m.mother_id in app.expanded_ids:
                visible.add(m.id)
                changed = True

            # 通过配偶可见（配偶的配偶）
            if not changed and m.id not in visible:
                for sp_attr in ("spouse1_id", "spouse2_id"):
                    sp_id = getattr(m, sp_attr, None)
                    if sp_id is not None and sp_id in visible:
                        visible.add(m.id)
                        changed = True
                        break

    return visible


def _has_any_children(app, member_id):
    """判断某成员是否有子女"""
    for m in app.members:
        if m.father_id == member_id or m.mother_id == member_id:
            return True
    return False


def _is_expanded(app, member_id):
    return member_id in app.expanded_ids


def _toggle_expand(app, member_id):
    """切换展开/折叠"""
    if member_id in app.expanded_ids:
        app.expanded_ids.discard(member_id)
    else:
        app.expanded_ids.add(member_id)
    draw_tree(app)


def _draw_node(app, member, x, y, visible_ids):
    """绘制单个成员节点（含展开按钮，绑定单击展开/双击详情）"""
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

    # 主矩形
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
    gen_display = member.generation if member.generation is not None else "?"
    app.tree_canvas.create_text(tx, y + 12,
                                 text=f"第{gen_display}代",
                                 font=("微软雅黑", 8), fill="#eee", tags=tag)

    # 展开/折叠指示器（有子女的节点才显示）
    if _has_any_children(app, member.id):
        expanded = _is_expanded(app, member.id)
        indicator = "−" if expanded else "+"
        ind_color = "#27ae60" if expanded else "#e67e22"
        ind_x = x + nw // 2 - 12
        ind_y = y + nh // 2 - 10
        app.tree_canvas.create_oval(
            ind_x - 8, ind_y - 8, ind_x + 8, ind_y + 8,
            fill=ind_color, outline="white", width=2, tags=tag
        )
        app.tree_canvas.create_text(
            ind_x, ind_y, text=indicator,
            font=("Arial", 11, "bold"), fill="white", tags=tag
        )

    # ── 事件绑定 ──────────────────────────────────────────
    def on_click(event, mid=member.id):
        if _has_any_children(app, mid):
            _toggle_expand(app, mid)
        else:
            app.show_member_detail(mid)

    def on_dblclick(event, mid=member.id):
        app.show_member_detail(mid)

    app.tree_canvas.tag_bind(tag, "<Button-1>", on_click)
    app.tree_canvas.tag_bind(tag, "<Double-Button-1>", on_dblclick)
    app.canvas_items[member.id] = tag


def zoom_tree(app, factor):
    """缩放家谱树"""
    app.scale *= factor
    app.scale = max(0.3, min(3.0, app.scale))
    app.tree_canvas.scale("all",
                           app.tree_canvas.winfo_width() // 2,
                           app.tree_canvas.winfo_height() // 2,
                           factor, factor)
