# -*- coding: utf-8 -*-
"""CSV 导入/导出模块 — v2.6d+ 批量导入+冲突检测"""
import csv
import os
import json
import shutil
from datetime import datetime
from tkinter import filedialog, messagebox

HEADERS = ["代次", "姓名", "性别", "出生日期", "逝世日期", "父亲姓名", "母亲姓名",
           "配偶1姓名", "配偶2姓名", "个人简介", "寸照路径"]


def _write_error_log(log_path, csv_path, errors):
    """写入出错.log"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        "=== 家谱CSV导入错误报告 ===",
        f"时间：{timestamp}",
        f"文件：{csv_path}",
        f"错误数：{len(errors)}",
        "",
    ]
    for idx, err in enumerate(errors, 1):
        lines.append(f"[错误{idx}] 第{err['row']}行「{err['name']}」")
        lines.append(f"  类型：{err['type']}")
        if err["type"] == "子女代次 <= 父亲代次":
            lines.append(f"  子女代次：{err['child_gen']}")
            lines.append(f"  父亲姓名：{err['parent_name']}（代次：{err['parent_gen']}）")
            lines.append(f"  提示：子女代次必须 > 父亲代次")
        elif err["type"] == "子女代次 <= 母亲代次":
            lines.append(f"  子女代次：{err['child_gen']}")
            lines.append(f"  母亲姓名：{err['parent_name']}（代次：{err['parent_gen']}）")
            lines.append(f"  提示：子女代次必须 > 母亲代次")
        elif err["type"] == "始祖代次错误":
            lines.append(f"  填写代次：{err['input_gen']}")
            lines.append(f"  提示：始祖（无父母无配偶者）代次必须为1")
        elif err["type"] == "配偶代次不一致":
            lines.append(f"  填写代次：{err['input_gen']}")
            lines.append(f"  配偶姓名：{err['spouse_name']}（代次：{err['spouse_gen']}）")
            lines.append(f"  提示：无父母有配偶者，代次必须与配偶相同")
        else:
            lines.append(f"  错误信息：{err.get('msg', '')}")
        lines.append("")

    with open(log_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def download_template():
    """下载 CSV 导入模板"""
    path = filedialog.asksaveasfilename(
        title="保存导入模板",
        defaultextension=".csv",
        filetypes=[("CSV文件", "*.csv")],
        initialfile="家谱导入模板.csv"
    )
    if not path:
        return
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(HEADERS)
        writer.writerow(["1", "关国安", "男", "1950-01", "", "", "", "", "", "家族长辈", "photos/guanguoan.jpg"])
        writer.writerow(["2", "关星星", "男", "1980-05", "", "关国安", "王双连", "李梅", "", "关家长子", ""])
    messagebox.showinfo("成功", f"模板已保存：\n{path}")


def export_csv(app):
    """导出所有成员为 CSV"""
    path = filedialog.asksaveasfilename(
        title="导出成员CSV",
        defaultextension=".csv",
        filetypes=[("CSV文件", "*.csv")],
        initialfile="家谱成员.csv"
    )
    if not path:
        return

    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(HEADERS)
        for m in app.members:
            father  = app.member_map[m.father_id].name  if m.father_id  and m.father_id  in app.member_map else ""
            mother  = app.member_map[m.mother_id].name  if m.mother_id  and m.mother_id  in app.member_map else ""
            sp1     = app.member_map[m.spouse1_id].name if m.spouse1_id and m.spouse1_id in app.member_map else ""
            sp2     = app.member_map[m.spouse2_id].name if m.spouse2_id and m.spouse2_id in app.member_map else ""
            writer.writerow([
                m.generation if m.generation is not None else 1,
                m.name, m.gender or "", m.birth_date or "", m.death_date or "",
                father, mother, sp1, sp2,
                m.bio or "", m.photo_path or ""
            ])

    messagebox.showinfo("成功", f"已导出 {len(app.members)} 位成员：\n{path}")


def import_csv(app):
    """从 CSV 导入成员（三步：入库→代次计算→冲突检测，失败全部回滚）"""
    path = filedialog.askopenfilename(
        title="选择导入文件",
        filetypes=[("CSV文件", "*.csv"), ("所有文件", "*.*")]
    )
    if not path:
        return

    # ── 读取文件 ──────────────────────────────────────────────
    rows = None
    last_err = None
    for enc in ["utf-8-sig", "gbk", "gb2312"]:
        try:
            with open(path, "r", encoding=enc) as f:
                rows = list(csv.reader(f))
            break
        except Exception as e:
            last_err = e
            continue
    if rows is None:
        messagebox.showerror("错误", f"读取文件失败：{last_err}")
        return

    if len(rows) < 2:
        messagebox.showwarning("提示", "CSV 文件内容为空或只有表头")
        return

    header = rows[0]
    if header != HEADERS:
        messagebox.showwarning("提示",
            f"表头格式不对，请使用「下载导入模板」生成的文件。\n\n期望：{HEADERS}\n实际：{header}")
        return

    data_rows = [r for r in rows[1:] if r and r[0].strip()]
    if not data_rows:
        messagebox.showwarning("提示", "没有可导入的数据行")
        return

    from .db import get_conn

    # 构建已有成员的索引
    existing_names = {}
    for m in app.members:
        existing_names.setdefault(m.name, []).append(m.id)
    # 简易查找表（同名取最后一位，解析父母/配偶用）
    name_to_id = {n: ids[-1] for n, ids in existing_names.items()}

    batch_ids  = {}    # 本次导入的 name -> id（用于回滚）
    batch_keys = set() # 本次导入的复合键（姓名|父亲|出生年），防同批次同名
    name_to_csv_gen = {}  # 本次导入的 name -> csv_gen（供配偶校验用）

    conn = get_conn()
    try:
        c = conn.cursor()
        parsed        = []
        parse_errors  = []

        # ══════════════════════════════════════════════════════
        # Step 1：整批解析 + 入库
        # ══════════════════════════════════════════════════════
        for i, row in enumerate(data_rows, start=2):
            try:
                gen_input   = row[0].strip()   # 代次（可选）
                name        = row[1].strip()
                gender      = row[2].strip()
                birth_date  = row[3].strip()
                death_date  = row[4].strip()
                father_name = row[5].strip()
                mother_name = row[6].strip()
                sp1_name    = row[7].strip()
                sp2_name    = row[8].strip()
                bio         = row[9].strip()
                photo_path  = row[10].strip()

                if not name:
                    parse_errors.append({
                        "row": i, "name": "(空)", "type": "空姓名",
                        "msg": "姓名为空，已跳过"
                    })
                    continue

                # ── 重名检测（复合键：姓名 + 父亲 + 出生年） ──
                dup_key = f"{name}|{father_name}|{birth_date[:4] if birth_date else ''}"
                if dup_key in batch_keys:
                    parse_errors.append({
                        "row": i, "name": name, "type": "批次内重名",
                        "msg": f"「{name}」在本批中已存在（父：{father_name}，出生：{birth_date}），已跳过"
                    })
                    continue
                # 检查已有成员
                if name in existing_names:
                    matched = False
                    for eid in existing_names[name]:
                        em = app.member_map.get(eid)
                        if em:
                            ef_name = app.member_map[em.father_id].name if em.father_id and em.father_id in app.member_map else None
                            if ef_name == (father_name or None) or (ef_name is None and not father_name):
                                matched = True
                                break
                    if matched:
                        parse_errors.append({
                            "row": i, "name": name, "type": "成员已存在",
                            "msg": f"「{name}」已存在（父：{father_name}），已跳过"
                        })
                        continue

                # 代次（可选：留空则自动计算，不校验）
                gen_input_int = None
                if gen_input:
                    try:
                        gen_input_int = int(gen_input)
                    except ValueError:
                        parse_errors.append({
                            "row": i, "name": name, "type": "代次格式错误",
                            "msg": f"代次「{gen_input}」不是有效整数，已跳过"
                        })
                        continue

                father_id = name_to_id.get(father_name) if father_name else None
                mother_id = name_to_id.get(mother_name) if mother_name else None
                sp1_id    = name_to_id.get(sp1_name)    if sp1_name    else None
                sp2_id    = name_to_id.get(sp2_name)    if sp2_name    else None

                # 使用原始 SQL INSERT，避免触发 calc_generations()
                # 初始 generation=0，后续 Step2 代次计算会覆盖
                c.execute("""
                    INSERT INTO members (name, gender, birth_date, death_date, father_id,
                    mother_id, spouse1_id, spouse2_id, bio, photo_path, extra_photos, generation)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    name, gender or None, birth_date or None, death_date or None,
                    father_id, mother_id, sp1_id, sp2_id,
                    bio, photo_path or None, "[]", 0   # 初始代次=0
                ))
                new_id = c.lastrowid
                conn.commit()
                name_to_id[name] = new_id
                batch_ids[name]  = new_id
                name_to_csv_gen[name] = gen_input_int
                batch_keys.add(dup_key)

                parsed.append({
                    "row": i, "name": name, "csv_gen": gen_input_int,
                    "father_id": father_id, "mother_id": mother_id,
                    "father_name": father_name, "mother_name": mother_name,
                    "sp1_name": sp1_name, "sp2_name": sp2_name,
                })

            except Exception as e:
                parse_errors.append({
                    "row": i,
                    "name": row[1] if len(row) > 1 else "(未知)",
                    "type": "解析异常",
                    "msg": str(e)
                })

        if parse_errors:
            # 有解析错误，入库的数据先保留；后续冲突检测也会失败而回滚
            pass

        # ══════════════════════════════════════════════════════
        # Step 2：代次计算（迭代至稳定）
        #   规则（1-based）：
        #     - 有父母 → max(父亲gen, 母亲gen) + 1
        #     - 无父母 + 有配偶 → 配偶gen
        #     - 无父母 + 无配偶（始祖）→ gen=1
        # ══════════════════════════════════════════════════════
        conn.commit()
        stable = False
        while not stable:
            stable = True

            # 2a. 父子代次计算
            for item in parsed:
                mid = batch_ids.get(item["name"])
                if mid is None:
                    continue
                c.execute("SELECT generation FROM members WHERE id=?", (mid,))
                r = c.fetchone()
                current_gen = r[0] if r else 0

                target_gen = None
                if item["father_id"] is not None:
                    c.execute("SELECT generation FROM members WHERE id=?",
                              (item["father_id"],))
                    r = c.fetchone()
                    if r and r[0] is not None and r[0] > 0:
                        target_gen = r[0] + 1
                if item["mother_id"] is not None:
                    c.execute("SELECT generation FROM members WHERE id=?",
                              (item["mother_id"],))
                    r = c.fetchone()
                    if r and r[0] is not None and r[0] > 0:
                        tg = r[0] + 1
                        if target_gen is None or tg > target_gen:
                            target_gen = tg

                if target_gen is not None and current_gen != target_gen:
                    c.execute("UPDATE members SET generation=? WHERE id=?",
                              (target_gen, mid))
                    stable = False

            # 2b. 配偶代次同步（无父母有配偶 → 配偶代次）
            for item in parsed:
                mid = batch_ids.get(item["name"])
                if mid is None:
                    continue
                if item["father_id"] is not None or item["mother_id"] is not None:
                    continue
                sp_names = [n for n in (item["sp1_name"], item["sp2_name"]) if n]
                if not sp_names:
                    continue

                spouse_gen = None
                for sn in sp_names:
                    if sn in batch_ids:
                        c.execute("SELECT generation FROM members WHERE id=?",
                                  (batch_ids[sn],))
                        r = c.fetchone()
                        spouse_gen = r[0] if r else None
                    else:
                        c.execute("SELECT generation FROM members WHERE name=?", (sn,))
                        r = c.fetchone()
                        spouse_gen = r[0] if r else None
                    if spouse_gen is not None and spouse_gen > 0:
                        break

                if spouse_gen is not None and spouse_gen > 0:
                    c.execute("SELECT generation FROM members WHERE id=?", (mid,))
                    r = c.fetchone()
                    current_gen = r[0] if r else 0
                    if current_gen != spouse_gen:
                        c.execute("UPDATE members SET generation=? WHERE id=?",
                                  (spouse_gen, mid))
                        stable = False

            # 2c. 无父母无配偶 → 1
            for item in parsed:
                mid = batch_ids.get(item["name"])
                if mid is None:
                    continue
                if item["father_id"] is None and item["mother_id"] is None:
                    sp_names = [n for n in (item["sp1_name"], item["sp2_name"]) if n]
                    if not sp_names:
                        c.execute("SELECT generation FROM members WHERE id=?", (mid,))
                        r = c.fetchone()
                        current_gen = r[0] if r else 0
                        if current_gen != 1:
                            c.execute("UPDATE members SET generation=1 WHERE id=?", (mid,))
                            stable = False

            if not stable:
                conn.commit()

        # ══════════════════════════════════════════════════════
        # Step 3：冲突检测（使用 csv_gen 进行校验）
        #   csv_gen = None → 跳过（用户留空，自动计算）
        #   csv_gen = 1 + 无父母 → 跳过（始祖/始祖配偶）
        #   csv_gen = 1 + 有父母 → 仍需校验①②（子女>父母）
        #   csv_gen ≠ 1 → 全部校验④
        # ══════════════════════════════════════════════════════
        conflict_errors = []

        for item in parsed:
            row_num = item["row"]
            name    = item["name"]
            csv_gen = item["csv_gen"]
            mid     = batch_ids.get(name)
            if mid is None:
                continue

            # 留空 → 不校验
            if csv_gen is None:
                continue

            has_parents = item["father_id"] is not None or item["mother_id"] is not None

            # 代次=1 且无父母：跳过校验（始祖/始祖配偶）
            if csv_gen == 1 and not has_parents:
                continue

            # ① 子女代次 > 父亲代次
            if item["father_id"] is not None:
                c.execute("SELECT generation FROM members WHERE id=?", (item["father_id"],))
                r = c.fetchone()
                if r and r[0] is not None:
                    father_gen = r[0]
                    if csv_gen <= father_gen:
                        conflict_errors.append({
                            "row": row_num, "name": name, "type": "子女代次 <= 父亲代次",
                            "child_gen": csv_gen, "parent_name": item["father_name"],
                            "parent_gen": father_gen,
                        })

            # ② 子女代次 > 母亲代次
            if item["mother_id"] is not None:
                c.execute("SELECT generation FROM members WHERE id=?", (item["mother_id"],))
                r = c.fetchone()
                if r and r[0] is not None:
                    mother_gen = r[0]
                    if csv_gen <= mother_gen:
                        conflict_errors.append({
                            "row": row_num, "name": name, "type": "子女代次 <= 母亲代次",
                            "child_gen": csv_gen, "parent_name": item["mother_name"],
                            "parent_gen": mother_gen,
                        })

            # ③ 无父母 + 无配偶 → csv_gen 必须=1
            if not has_parents:
                sp_names = [n for n in (item["sp1_name"], item["sp2_name"]) if n]
                if not sp_names:
                    if csv_gen != 1:
                        conflict_errors.append({
                            "row": row_num, "name": name, "type": "始祖代次错误",
                            "input_gen": csv_gen,
                        })

                # ④ 无父母 + 有配偶 → csv_gen 必须与配偶代次相同
                # 注意：比较的是 CSV 声明的代次（name_to_csv_gen），而非数据库计算值
                else:
                    for sn in sp_names:
                        if sn in name_to_csv_gen:
                            spouse_gen = name_to_csv_gen[sn]
                        else:
                            # 配偶为已有成员，查数据库
                            c.execute("SELECT generation FROM members WHERE name=?", (sn,))
                            r = c.fetchone()
                            spouse_gen = r[0] if r else None
                        if spouse_gen is not None:
                            if csv_gen != spouse_gen:
                                conflict_errors.append({
                                    "row": row_num, "name": name, "type": "配偶代次不一致",
                                    "input_gen": csv_gen, "spouse_name": sn,
                                    "spouse_gen": spouse_gen,
                                })
                            break

    finally:
        conn.close()

    # ── 处理结果 ─────────────────────────────────────────────
    all_errors = parse_errors + conflict_errors

    if all_errors:
        # 回滚：删除本次导入的所有行
        if batch_ids:
            conn2 = get_conn()
            try:
                c2 = conn2.cursor()
                for mid in batch_ids.values():
                    c2.execute("DELETE FROM members WHERE id=?", (mid,))
                conn2.commit()
            finally:
                conn2.close()

        # 写出错.log
        log_dir  = os.path.dirname(path) or "."
        log_path = os.path.join(log_dir, "出错.log")
        _write_error_log(log_path, path, all_errors)

        # 弹框
        err_summary = "\n".join(
            [f"第{e['row']}行「{e['name']}」：{e['type']}" for e in all_errors[:10]]
        )
        if len(all_errors) > 10:
            err_summary += f"\n... 共 {len(all_errors)} 条错误"
        messagebox.showerror("导入失败",
            f"共发现 {len(all_errors)} 个错误，导入已取消。\n"
            f"详细报告已写入：\n{log_path}\n\n"
            f"错误摘要：\n{err_summary}")
        return

    # ── 双向配偶关联 ────────────────────────────────────────
    conn3 = get_conn()
    try:
        c3 = conn3.cursor()
        for name, mid in batch_ids.items():
            c3.execute("SELECT spouse1_id, spouse2_id FROM members WHERE id=?", (mid,))
            row = c3.fetchone()
            if row:
                for sid in (row[0], row[1]):
                    if sid:  # 有配偶
                        c3.execute("SELECT spouse1_id, spouse2_id FROM members WHERE id=?", (sid,))
                        srow = c3.fetchone()
                        if srow:
                            if mid not in (srow[0], srow[1]):  # 对方尚未关联自己
                                if srow[0] is None:
                                    c3.execute("UPDATE members SET spouse1_id=? WHERE id=?", (mid, sid))
                                elif srow[1] is None:
                                    c3.execute("UPDATE members SET spouse2_id=? WHERE id=?", (mid, sid))
        conn3.commit()
    finally:
        conn3.close()

    app.load_data()

    imported_count = len(parsed) - len(conflict_errors)
    msg = f"导入完成！\n成功：{imported_count} 人"
    if parse_errors:
        msg += f"\n跳过（解析错误）：{len(parse_errors)} 条"
    messagebox.showinfo("导入结果", msg)


# ══════════════════════════════════════════════════════════════════════════════
# 故事集批量导出 / 导入
# ══════════════════════════════════════════════════════════════════════════════

def export_stories(app):
    """导出所有故事为 JSON（含配图文件复制到同名目录）"""
    from .models import get_all_stories

    path = filedialog.asksaveasfilename(
        title="导出故事集",
        defaultextension=".json",
        filetypes=[("JSON文件", "*.json")],
        initialfile="家谱故事集.json"
    )
    if not path:
        return

    stories = get_all_stories()
    if not stories:
        messagebox.showwarning("提示", "暂无故事可导出")
        return

    member_map = {m.id: m.name for m in app.members}
    export_dir = os.path.splitext(path)[0] + "_files"
    os.makedirs(export_dir, exist_ok=True)

    records = []
    for s in stories:
        img_basename = ""
        if s.image_path and os.path.exists(s.image_path):
            img_basename = os.path.basename(s.image_path)
            dest = os.path.join(export_dir, img_basename)
            counter = 1
            base, ext = os.path.splitext(img_basename)
            while os.path.exists(dest):
                img_basename = f"{base}_{counter}{ext}"
                dest = os.path.join(export_dir, img_basename)
                counter += 1
            shutil.copy2(s.image_path, dest)

        records.append({
            "title":       s.title,
            "content":     s.content or "",
            "author":      s.author or "",
            "created_at":  s.created_at or "",
            "member_name": member_map.get(s.member_id, ""),
            "image_path":  img_basename,
        })

    manifest = {"version": 1, "stories": records}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    messagebox.showinfo("成功",
        f"已导出 {len(stories)} 条故事\n"
        f"主文件：{path}\n"
        f"图片目录：{export_dir}")


def import_stories(app):
    """从 JSON 批量导入故事（支持配图，每故事最多1张）"""
    path = filedialog.askopenfilename(
        title="选择故事集文件",
        filetypes=[("JSON文件", "*.json"), ("所有文件", "*.*")]
    )
    if not path:
        return

    raw = None
    for enc in ("utf-8", "utf-8-sig"):
        try:
            with open(path, "r", encoding=enc) as f:
                raw = f.read()
            break
        except Exception:
            continue
    if raw is None:
        messagebox.showerror("错误", "无法读取文件，请确认文件编码为 UTF-8")
        return

    try:
        data = json.loads(raw)
    except Exception as e:
        messagebox.showerror("错误", f"JSON 格式错误：{e}")
        return

    records = data.get("stories", [])
    if not records:
        messagebox.showwarning("提示", "文件中没有故事记录")
        return

    json_dir = os.path.dirname(path) or "."
    json_name = os.path.splitext(os.path.basename(path))[0]
    img_dir = os.path.join(json_dir, json_name + "_files")

    from .models import save_story

    member_name_to_id = {m.name: m.id for m in app.members}
    imported = skipped = 0
    errors = []

    for i, rec in enumerate(records, start=1):
        try:
            title = str(rec.get("title") or "").strip()
            content = str(rec.get("content") or "").strip()
            if not title or not content:
                skipped += 1
                continue

            author = str(rec.get("author") or "").strip() or None
            created = str(rec.get("created_at") or "").strip() or None

            member_name = str(rec.get("member_name") or "").strip()
            member_id = member_name_to_id.get(member_name) if member_name else None

            img_basename = str(rec.get("image_path") or "").strip()
            img_path = None
            if img_basename:
                img_full = os.path.join(img_dir, img_basename)
                if os.path.exists(img_full):
                    img_path = img_full
                else:
                    errors.append(f"第{i}条「{title}」：图片不存在，已跳过图片\n  期望路径：{img_full}")

            save_story({
                "title":      title,
                "content":    content,
                "author":     author,
                "created_at": created,
                "member_id":  member_id,
                "image_path": img_path,
            })
            imported += 1

        except Exception as e:
            errors.append(f"第{i}条：{e}")
            skipped += 1

    msg = f"导入完成！\n成功：{imported} 条\n跳过：{skipped} 条"
    if errors:
        msg += f"\n警告：{len(errors)} 条\n" + "\n".join(errors[:5])
    messagebox.showinfo("导入结果", msg)


# ══════════════════════════════════════════════════════════════════════════════
# 一键备份 / 恢复
# ══════════════════════════════════════════════════════════════════════════════

def backup_all(app):
    """一键备份：成员+故事+照片墙+所有图片文件"""
    from .models import get_all_stories, get_all_wall_photos

    base = filedialog.askdirectory(title="选择备份目录")
    if not base:
        return

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak_dir = os.path.join(base, f"家谱备份_{stamp}")
    os.makedirs(bak_dir, exist_ok=True)

    # 图片子目录
    photos_dir = os.path.join(bak_dir, "photos")
    member_photos_dir = os.path.join(bak_dir, "member_photos")
    story_images_dir = os.path.join(bak_dir, "story_images")
    os.makedirs(photos_dir)
    os.makedirs(member_photos_dir)
    os.makedirs(story_images_dir)

    # 1. 导出成员 CSV
    csv_path = os.path.join(bak_dir, "members.csv")
    _backup_csv(app, csv_path)

    # 2. 复制 photos/ 目录
    src_photos = os.path.join(os.path.dirname(__file__), "..", "photos")
    if os.path.exists(src_photos):
        for fname in os.listdir(src_photos):
            src_f = os.path.join(src_photos, fname)
            if not os.path.isfile(src_f):
                continue
            shutil.copy2(src_f,
                         os.path.join(photos_dir, fname))

    # 3. 复制成员寸照 + extra_photos
    for m in app.members:
        for src_path in [m.photo_path] + (m.extra_photos or []):
            if src_path and os.path.exists(src_path):
                try:
                    shutil.copy2(src_path, os.path.join(member_photos_dir,
                                os.path.basename(src_path)))
                except:
                    pass

    # 4. 导出故事 + 复制配图
    stories = get_all_stories()
    for s in stories:
        if s.image_path and os.path.exists(s.image_path):
            try:
                shutil.copy2(s.image_path, os.path.join(story_images_dir,
                            os.path.basename(s.image_path)))
            except:
                pass
    _backup_stories_json(stories, app.member_map, bak_dir)

    # 5. 导出照片墙元数据
    wall_photos = get_all_wall_photos()
    _backup_photo_wall_json(wall_photos, bak_dir)

    messagebox.showinfo("备份完成",
        f"已备份到：{bak_dir}\n"
        f"包含：{len(app.members)} 位成员、"
        f"{len(stories)} 条故事、"
        f"{len(wall_photos)} 张照片墙照片")


def _backup_csv(app, csv_path):
    """写入 members.csv"""
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(HEADERS)
        for m in app.members:
            father  = app.member_map[m.father_id].name  if m.father_id  and m.father_id  in app.member_map else ""
            mother  = app.member_map[m.mother_id].name  if m.mother_id  and m.mother_id  in app.member_map else ""
            sp1     = app.member_map[m.spouse1_id].name if m.spouse1_id and m.spouse1_id in app.member_map else ""
            sp2     = app.member_map[m.spouse2_id].name if m.spouse2_id and m.spouse2_id in app.member_map else ""
            w.writerow([
                m.generation if m.generation is not None else 1,
                m.name, m.gender or "", m.birth_date or "", m.death_date or "",
                father, mother, sp1, sp2,
                m.bio or "",
                os.path.basename(m.photo_path) if m.photo_path else "",
            ])


def _backup_stories_json(stories, member_map, bak_dir):
    """写入 stories.json"""
    records = []
    for s in stories:
        records.append({
            "title": s.title, "content": s.content or "",
            "author": s.author or "", "created_at": s.created_at or "",
            "member_name": member_map[s.member_id].name if s.member_id and s.member_id in member_map else "",
            "image_basename": os.path.basename(s.image_path) if s.image_path else "",
        })
    with open(os.path.join(bak_dir, "stories.json"), "w", encoding="utf-8") as f:
        json.dump({"version": 1, "stories": records}, f, ensure_ascii=False, indent=2)


def _backup_photo_wall_json(wall_photos, bak_dir):
    """写入 photo_wall.json"""
    records = []
    for p in wall_photos:
        records.append({
            "file_basename": os.path.basename(p.file_path),
            "caption": p.caption or "",
            "member_ids": p.get_member_ids(),
            "sort_order": p.sort_order or 0,
        })
    with open(os.path.join(bak_dir, "photo_wall.json"), "w", encoding="utf-8") as f:
        json.dump({"version": 1, "photos": records}, f, ensure_ascii=False, indent=2)


def restore_all(app):
    """一键恢复：从备份目录恢复全部数据"""
    from .db import get_conn
    from .models import save_story, delete_member

    bak_dir = filedialog.askdirectory(title="选择备份目录（家谱备份_XXX）")
    if not bak_dir:
        return

    # 检查备份完整性
    required = ["members.csv", "photo_wall.json"]
    for fn in required:
        if not os.path.exists(os.path.join(bak_dir, fn)):
            messagebox.showerror("错误", f"备份目录缺少 {fn}，无法恢复")
            return

    if not messagebox.askyesno("⚠️ 确认恢复",
        "恢复操作将清空当前所有数据，替换为备份内容。\n\n"
        "建议：先进行一次备份再恢复。\n\n"
        "确定要恢复吗？"):
        return

    if not messagebox.askyesno("再次确认",
        "当前所有数据将被删除并替换！\n此操作不可撤销！\n\n确定继续？"):
        return

    # 恢复图片目录
    photos_dir = os.path.join(bak_dir, "photos")
    member_photos_dir = os.path.join(bak_dir, "member_photos")
    story_images_dir = os.path.join(bak_dir, "story_images")

    app_photos = os.path.join(os.path.dirname(__file__), "..", "photos")
    if os.path.exists(photos_dir):
        os.makedirs(app_photos, exist_ok=True)
        for fname in os.listdir(photos_dir):
            shutil.copy2(os.path.join(photos_dir, fname),
                         os.path.join(app_photos, fname))

    # Step 1：清空数据库
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("DELETE FROM stories")
        c.execute("DELETE FROM photo_wall")
        c.execute("DELETE FROM members")
        conn.commit()
    finally:
        conn.close()

    app.load_data()  # 清空后重新加载

    # Step 2：导入成员
    csv_path = os.path.join(bak_dir, "members.csv")
    import_csv_internal(app, csv_path, member_photos_dir)
    app.load_data()

    # Step 3：导入照片墙
    pj_path = os.path.join(bak_dir, "photo_wall.json")
    with open(pj_path, "r", encoding="utf-8") as f:
        pw_data = json.load(f)
    _restore_photo_wall(app, pw_data.get("photos", []), photos_dir)
    app.load_data()

    # Step 4：导入故事
    sj_path = os.path.join(bak_dir, "stories.json")
    if os.path.exists(sj_path):
        with open(sj_path, "r", encoding="utf-8") as f:
            st_data = json.load(f)
        _restore_stories(app, st_data.get("stories", []), story_images_dir)

    app.load_data()
    messagebox.showinfo("恢复完成", "所有数据已从备份恢复")


def import_csv_internal(app, csv_path, member_photos_dir):
    """内部导入 CSV（不走界面选文件），同步恢复成员寸照路径"""
    from .db import get_conn
    from .models import save_member, calc_generations

    csv_rows = []
    for enc in ["utf-8-sig", "gbk", "gb2312"]:
        try:
            with open(csv_path, "r", encoding=enc) as f:
                csv_rows = list(csv.reader(f))
            break
        except:
            continue
    if len(csv_rows) < 2:
        return

    data_rows = [r for r in csv_rows[1:] if r and r[0].strip()]
    name_to_id = {m.name: m.id for m in app.members}
    imported = 0

    for row in data_rows:
        name = row[1].strip()
        if not name:
            continue
        photo_bn = row[10].strip() if len(row) > 10 else ""
        photo_path = ""
        if photo_bn:
            candidate = os.path.join(member_photos_dir, photo_bn)
            if os.path.exists(candidate):
                photo_path = candidate
            else:
                alt = os.path.join(os.path.dirname(__file__), "..", "photos", photo_bn)
                if os.path.exists(alt):
                    photo_path = alt

        gen_int = row[0].strip()
        data = {
            "name": name,
            "gender": row[2].strip() or None,
            "birth_date": row[3].strip() or None,
            "death_date": row[4].strip() or None,
            "father_id": name_to_id.get(row[5].strip()) if row[5].strip() else None,
            "mother_id": name_to_id.get(row[6].strip()) if row[6].strip() else None,
            "spouse1_id": name_to_id.get(row[7].strip()) if row[7].strip() else None,
            "spouse2_id": name_to_id.get(row[8].strip()) if row[8].strip() else None,
            "bio": row[9].strip(),
            "photo_path": photo_path or None,
            "extra_photos": [],
            "generation": int(gen_int) if gen_int else None,
        }
        new_id = save_member(data)
        name_to_id[name] = new_id
        imported += 1

    # 双向配偶关联
    conn = get_conn()
    try:
        c = conn.cursor()
        for name, mid in list(name_to_id.items()):
            c.execute("SELECT spouse1_id, spouse2_id FROM members WHERE id=?", (mid,))
            r = c.fetchone()
            if r:
                for sid in (r[0], r[1]):
                    if sid:
                        c.execute("SELECT spouse1_id, spouse2_id FROM members WHERE id=?", (sid,))
                        sr = c.fetchone()
                        if sr and mid not in (sr[0], sr[1]):
                            if sr[0] is None:
                                c.execute("UPDATE members SET spouse1_id=? WHERE id=?", (mid, sid))
                            elif sr[1] is None:
                                c.execute("UPDATE members SET spouse2_id=? WHERE id=?", (mid, sid))
        conn.commit()
    finally:
        conn.close()

    print(f"恢复导入 {imported} 位成员")


def _restore_photo_wall(app, photos_data, photos_dir):
    """恢复照片墙数据"""
    from .db import get_conn
    name_to_id = {m.name: m.id for m in app.members}
    conn = get_conn()
    try:
        c = conn.cursor()
        for item in photos_data:
            bn = item.get("file_basename", "")
            src = os.path.join(photos_dir, bn) if os.path.exists(os.path.join(photos_dir, bn)) else ""
            if not src and bn:
                alt = os.path.join(os.path.dirname(__file__), "..", "photos", bn)
                if os.path.exists(alt):
                    src = alt
                else:
                    continue
            if not src:
                continue

            mid = None
            mids = item.get("member_ids", [])
            if mids and mids[0] in name_to_id:
                mid = name_to_id.get(mids[0])

            c.execute(
                "INSERT INTO photo_wall (file_path, caption, member_id, member_ids, sort_order) "
                "VALUES (?,?,?,?,?)",
                (src, item.get("caption", ""), mid,
                 json.dumps(mids) if mids else "[]",
                 item.get("sort_order", 0))
            )
        conn.commit()
    finally:
        conn.close()


def _restore_stories(app, stories_data, images_dir):
    """恢复故事数据"""
    from .models import save_story
    name_to_id = {m.name: m.id for m in app.members}
    for item in stories_data:
        img_path = None
        bn = item.get("image_basename", "")
        if bn:
            candidate = os.path.join(images_dir, bn)
            if os.path.exists(candidate):
                img_path = candidate
        mid = None
        mn = item.get("member_name", "")
        if mn and mn in name_to_id:
            mid = name_to_id[mn]
        save_story({
            "title": item.get("title", ""),
            "content": item.get("content", ""),
            "author": item.get("author") or None,
            "created_at": item.get("created_at") or None,
            "member_id": mid,
            "image_path": img_path,
        })
