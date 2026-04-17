# -*- coding: utf-8 -*-
"""CSV 导入/导出模块"""
import csv
import os
import json
import shutil
from tkinter import filedialog, messagebox

HEADERS = ["姓名", "性别", "出生日期", "逝世日期", "父亲姓名", "母亲姓名",
           "配偶1姓名", "配偶2姓名", "个人简介", "寸照路径", "代次"]


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
        writer.writerow(["关国安", "男", "1950-01", "", "关大海", "王秀英", "", "", "家族长辈", "photos/guanguoan.jpg"])
        writer.writerow(["关星星", "男", "1980-05", "", "关国安", "王双连", "李梅", "", "关家长子", "", "1"])
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
                m.name, m.gender or "", m.birth_date or "", m.death_date or "",
                father, mother, sp1, sp2,
                m.bio or "", m.photo_path or "", m.generation if m.generation is not None else 0
            ])

    messagebox.showinfo("成功", f"已导出 {len(app.members)} 位成员：\n{path}")


def import_csv(app):
    """从 CSV 导入成员"""
    path = filedialog.askopenfilename(
        title="选择导入文件",
        filetypes=[("CSV文件", "*.csv"), ("所有文件", "*.*")]
    )
    if not path:
        return

    # 自动检测编码
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

    from .models import save_member
    from .db import get_conn

    name_to_id = {m.name: m.id for m in app.members}
    imported = skipped = 0
    errors = []

    for i, row in enumerate(data_rows, start=2):
        try:
            name        = row[0].strip()
            gender      = row[1].strip()
            birth_date  = row[2].strip()
            death_date  = row[3].strip()
            father_name = row[4].strip()
            mother_name = row[5].strip()
            sp1_name    = row[6].strip()
            sp2_name    = row[7].strip()
            bio         = row[8].strip()
            photo_path  = row[9].strip()
            gen_input   = row[10].strip()   # 代次（可选）

            if not name:
                skipped += 1
                continue

            if name in name_to_id:
                skipped += 1
                continue

            # 解析代次（允许空）
            gen_input_int = None
            if gen_input:
                try:
                    gen_input_int = int(gen_input)
                except ValueError:
                    errors.append(f"第{i}行「{name}」：代次「{gen_input}」不是有效整数，跳过该行")
                    skipped += 1
                    continue

            data = {
                "name":        name,
                "gender":      gender or None,
                "birth_date":  birth_date or None,
                "death_date":  death_date or None,
                "father_id":   name_to_id.get(father_name) if father_name else None,
                "mother_id":   name_to_id.get(mother_name) if mother_name else None,
                "spouse1_id":  name_to_id.get(sp1_name)    if sp1_name    else None,
                "spouse2_id":  name_to_id.get(sp2_name)    if sp2_name    else None,
                "bio":         bio,
                "photo_path":  photo_path or None,
                "extra_photos": [],
                "generation":  gen_input_int,
            }
            new_id = save_member(data, member_id=None)
            name_to_id[name] = new_id

            # ── 代次冲突校验 ──────────────────────────────
            # 填写了 father_id 和 代次 时校验：子女代次必须 > 父亲代次
            if data["father_id"] is not None and gen_input_int is not None:
                from .db import get_conn as _gc
                _conn2 = _gc()
                _c2 = _conn2.cursor()
                _c2.execute("SELECT generation FROM members WHERE id=?", (data["father_id"],))
                _father_row = _c2.fetchone()
                _conn2.close()
                if _father_row:
                    father_gen = _father_row[0] or 0
                    if gen_input_int <= father_gen:
                        errors.append(
                            f"第{i}行「{name}」：代次冲突！"
                            f"子女代次({gen_input_int})必须大于父亲代次({father_gen})。"
                            f"已跳过。"
                        )
                        skipped += 1
                        # 回滚刚插入的成员
                        from .db import get_conn as _gc3
                        _rc = _gc3()
                        _rc.cursor().execute("DELETE FROM members WHERE id=?", (new_id,))
                        _rc.commit()
                        _rc.close()
                        del name_to_id[name]
                        imported -= 1
                        continue
            # ── 代次冲突校验结束 ────────────────────────

            imported += 1

        except Exception as e:
            errors.append(f"第{i}行：{e}")
            skipped += 1

    # 双向配偶关联
    conn = get_conn()
    c = conn.cursor()
    for name, mid in name_to_id.items():
        c.execute("SELECT spouse1_id, spouse2_id FROM members WHERE id=?", (mid,))
        row = c.fetchone()
        if row:
            for sid in (row[0], row[1]):
                if sid and sid not in (row[0], row[1]):
                    c.execute("SELECT spouse1_id, spouse2_id FROM members WHERE id=?", (sid,))
                    srow = c.fetchone()
                    if srow:
                        if srow[0] is None:
                            c.execute("UPDATE members SET spouse1_id=? WHERE id=?", (mid, sid))
                        elif srow[1] is None:
                            c.execute("UPDATE members SET spouse2_id=? WHERE id=?", (mid, sid))
    conn.commit()
    conn.close()

    app.load_data()

    msg = f"导入完成！\n成功：{imported} 人\n跳过：{skipped} 人"
    if errors:
        msg += f"\n错误：{len(errors)} 条\n" + "\n".join(errors[:5])
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
            # 复制图片到导出目录
            img_basename = os.path.basename(s.image_path)
            dest = os.path.join(export_dir, img_basename)
            # 防止文件名冲突（同名图片可能来自不同成员）
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
            "member_name": member_map.get(s.member_id, ""),  # 导出成员名而非ID
            "image_path":  img_basename,   # 仅存文件名，导入时从同目录读取
        })

    manifest = {"version": 1, "stories": records}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    messagebox.showinfo("成功",
        f"已导出 {len(stories)} 条故事\n"
        f"主文件：{path}\n"
        f"图片目录：{export_dir}\n\n"
        f"注意：导入时请保持「家谱故事集.json」和「家谱故事集_files」同级目录")


def import_stories(app):
    """从 JSON 批量导入故事（支持配图，每故事最多1张）"""
    path = filedialog.askopenfilename(
        title="选择故事集文件",
        filetypes=[("JSON文件", "*.json"), ("所有文件", "*.*")]
    )
    if not path:
        return

    # 自动检测编码
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

    # 配图目录：与 JSON 同级的 _files 目录
    json_dir = os.path.dirname(path) or "."
    json_name = os.path.splitext(os.path.basename(path))[0]  # 如 "家谱故事集"
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

            # 成员名 → ID
            member_name = str(rec.get("member_name") or "").strip()
            member_id = member_name_to_id.get(member_name) if member_name else None

            # 图片路径（最多1张）
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
