# -*- coding: utf-8 -*-
"""数据模型 + 查询函数"""
import json
from .db import get_conn


MEMBER_COLS = (
    "id, name, gender, birth_date, death_date, father_id, mother_id, "
    "bio, photo_path, extra_photos, generation, x_pos, y_pos, "
    "created_at, spouse_id, spouse1_id, spouse2_id"
)


class Member:
    """成员数据模型"""
    def __init__(self, row):
        self.id = row[0]
        self.name = row[1]
        self.gender = row[2]
        self.birth_date = row[3]
        self.death_date = row[4]
        self.father_id = row[5]
        self.mother_id = row[6]
        self.bio = row[7]
        self.photo_path = row[8]
        self.extra_photos = json.loads(row[9]) if row[9] else []
        self.generation = row[10]
        self.x_pos = row[11]
        self.y_pos = row[12]
        self.spouse_id = row[14]       # 旧字段（废弃但保留）
        self.spouse1_id = row[15]
        self.spouse2_id = row[16] if len(row) > 16 else None


class WallPhoto:
    """照片墙照片数据模型"""
    def __init__(self, row):
        self.id = row[0]
        self.file_path = row[1]
        self.caption = row[2]
        self.member_id = row[3]
        self.sort_order = row[4]
        self.member_ids = json.loads(row[6]) if len(row) > 6 and row[6] else []

    def get_member_ids(self):
        """获取关联的所有成员 ID 列表"""
        ids = list(self.member_ids) if self.member_ids else []
        if self.member_id and self.member_id not in ids:
            ids.append(self.member_id)
        return ids


def get_all_members():
    """获取所有成员"""
    conn = get_conn()
    c = conn.cursor()
    c.execute(f"SELECT {MEMBER_COLS} FROM members ORDER BY generation, id")
    rows = c.fetchall()
    conn.close()
    return [Member(row) for row in rows]


def get_member_by_id(member_id):
    """根据ID获取单个成员"""
    conn = get_conn()
    c = conn.cursor()
    c.execute(f"SELECT {MEMBER_COLS} FROM members WHERE id=?", (member_id,))
    row = c.fetchone()
    conn.close()
    return Member(row) if row else None


def get_all_wall_photos():
    """获取所有照片墙照片"""
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM photo_wall ORDER BY sort_order, id")
    rows = c.fetchall()
    conn.close()
    return [WallPhoto(row) for row in rows]


def save_member(data, member_id=None):
    """保存成员（新增或更新）"""
    conn = get_conn()
    try:
        c = conn.cursor()
        if member_id is None:
            c.execute("""
                INSERT INTO members (name, gender, birth_date, death_date, father_id,
                mother_id, spouse1_id, spouse2_id, bio, photo_path, extra_photos, generation)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data['name'], data.get('gender'), data.get('birth_date'),
                data.get('death_date'), data.get('father_id'), data.get('mother_id'),
                data.get('spouse1_id'), data.get('spouse2_id'),
                data.get('bio'), data.get('photo_path'),
                json.dumps(data.get('extra_photos', [])),
                data.get('generation', 0)
            ))
        else:
            c.execute("""
                UPDATE members SET name=?, gender=?, birth_date=?, death_date=?,
                father_id=?, mother_id=?, spouse1_id=?, spouse2_id=?, bio=?, photo_path=?,
                extra_photos=?, generation=?
                WHERE id=?
            """, (
                data['name'], data.get('gender'), data.get('birth_date'),
                data.get('death_date'), data.get('father_id'), data.get('mother_id'),
                data.get('spouse1_id'), data.get('spouse2_id'),
                data.get('bio'), data.get('photo_path'),
                json.dumps(data.get('extra_photos', [])),
                data.get('generation', 0),
                member_id
            ))
        conn.commit()
        member_id_out = c.lastrowid if member_id is None else member_id
    finally:
        conn.close()
    calc_generations()
    return member_id_out


def delete_member(member_id):
    """删除成员"""
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("UPDATE members SET father_id=NULL WHERE father_id=?", (member_id,))
        c.execute("UPDATE members SET mother_id=NULL WHERE mother_id=?", (member_id,))
        c.execute("UPDATE members SET spouse1_id=NULL WHERE spouse1_id=?", (member_id,))
        c.execute("UPDATE members SET spouse2_id=NULL WHERE spouse2_id=?", (member_id,))
        c.execute("DELETE FROM members WHERE id=?", (member_id,))
        conn.commit()
    finally:
        conn.close()
    calc_generations()


def delete_wall_photo(photo_id):
    """删除照片墙照片"""
    from .config import PHOTO_DIR
    import os
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT file_path FROM photo_wall WHERE id=?", (photo_id,))
    row = c.fetchone()
    if row and row[0] and os.path.exists(row[0]):
        try:
            os.remove(row[0])
        except:
            pass
    c.execute("DELETE FROM photo_wall WHERE id=?", (photo_id,))
    conn.commit()
    conn.close()


# ── 照片墙顺序管理 ──────────────────────────────────────────────────

def save_photo_order(ordered_ids):
    """
    保存照片墙顺序。
    ordered_ids: [photo_id, photo_id, ...] 按新顺序排列
    会将 sort_order 更新为列表中的位置（从 1 开始）。
    """
    conn = get_conn()
    c = conn.cursor()
    for idx, pid in enumerate(ordered_ids, start=1):
        c.execute("UPDATE photo_wall SET sort_order=? WHERE id=?", (idx, pid))
    conn.commit()
    conn.close()


def export_photo_order():
    """
    导出照片墙顺序为 dict: {photo_id: sort_order, ...}
    返回 dict，空时返回空字典。
    """
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id, sort_order FROM photo_wall ORDER BY sort_order, id")
    rows = c.fetchall()
    conn.close()
    return {str(r[0]): r[1] for r in rows}


def import_photo_order(order_dict):
    """
    根据导入的顺序 dict 更新 photo_wall.sort_order。
    order_dict: {str(photo_id): sort_order, ...}
    返回成功更新的条数。
    """
    conn = get_conn()
    c = conn.cursor()
    count = 0
    for pid_str, sort_val in order_dict.items():
        try:
            pid = int(pid_str)
            c.execute("UPDATE photo_wall SET sort_order=? WHERE id=?", (sort_val, pid))
            if c.rowcount > 0:
                count += 1
        except:
            pass
    conn.commit()
    conn.close()
    return count


def get_all_wall_photos_ordered():
    """获取所有照片墙照片（按 sort_order 升序，与 get_all_wall_photos 相同）"""
    return get_all_wall_photos()


def calc_generations():
    """
    计算所有成员的代次（generation）并写入数据库。
    规则（1-based）：
      - 无父无母（始祖）     → generation = 1
      - 有父母               → max(父亲gen, 母亲gen) + 1
      - 无父母 + 有配偶      → 配偶gen（迭代至稳定）
    """
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute("SELECT id, father_id, mother_id, spouse1_id, spouse2_id FROM members")
        rows = c.fetchall()
    finally:
        conn.close()

    if not rows:
        return

    # 内存关系映射：id -> {father, mother, spouses}
    rel = {}
    for r in rows:
        mid, fid, moid, sp1, sp2 = r
        rel[mid] = {
            "father": fid, "mother": moid,
            "spouses": [s for s in (sp1, sp2) if s is not None],
        }

    gen_map = {}  # id -> generation

    # ── 阶段1：父子代次计算（迭代拓扑排序）──
    # 初始：无父无母 = 1（始祖）
    for mid, info in rel.items():
        if info["father"] is None and info["mother"] is None:
            gen_map[mid] = 1

    # 迭代处理「父母代次已知」的成员
    changed = True
    while changed:
        changed = False
        for mid, info in rel.items():
            if mid in gen_map:
                continue
            parent_gens = []
            if info["father"] is not None and info["father"] in gen_map:
                parent_gens.append(gen_map[info["father"]])
            if info["mother"] is not None and info["mother"] in gen_map:
                parent_gens.append(gen_map[info["mother"]])
            if not parent_gens:
                continue
            gen_map[mid] = max(parent_gens) + 1
            changed = True

    # ── 阶段2：配偶代次同步（迭代至稳定）──
    # 无父母 + 有配偶 → 同步为配偶代次
    changed = True
    while changed:
        changed = False
        for mid, info in rel.items():
            if mid not in gen_map:
                continue
            if info["father"] is not None or info["mother"] is not None:
                continue  # 有父母者，代次由父子关系决定
            for sp_id in info["spouses"]:
                if sp_id in gen_map and gen_map[sp_id] != gen_map[mid]:
                    gen_map[mid] = gen_map[sp_id]
                    changed = True

    # ── 阶段3：孤岛成员（无父母无配偶）→ 1 ──
    for mid in rel:
        if mid not in gen_map:
            gen_map[mid] = 1

    # ── 批量写回数据库 ──
    conn2 = get_conn()
    try:
        c2 = conn2.cursor()
        for mid, gen in gen_map.items():
            c2.execute("UPDATE members SET generation=? WHERE id=?", (gen, mid))
        conn2.commit()
    finally:
        conn2.close()


# ── 故事摘要 ──────────────────────────────────────────────────

class Story:
    """故事摘要数据模型"""
    def __init__(self, row):
        self.id = row[0]
        self.title = row[1]
        self.content = row[2]
        self.author = row[3]
        self.created_at = row[4]
        self.member_id = row[5]
        self.image_path = row[6] if len(row) > 6 else None


def get_all_stories():
    """获取所有故事（按创建时间倒序）"""
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id, title, content, author, created_at, member_id, image_path "
              "FROM stories ORDER BY created_at DESC, id DESC")
    rows = c.fetchall()
    conn.close()
    return [Story(row) for row in rows]


def get_story_by_id(story_id):
    """根据ID获取单个故事"""
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id, title, content, author, created_at, member_id, image_path "
              "FROM stories WHERE id=?", (story_id,))
    row = c.fetchone()
    conn.close()
    return Story(row) if row else None


def save_story(data, story_id=None):
    """保存故事（新增或更新）"""
    conn = get_conn()
    c = conn.cursor()
    if story_id is None:
        c.execute("""
            INSERT INTO stories (title, content, author, created_at, member_id, image_path)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            data["title"],
            data["content"],
            data.get("author"),
            data.get("created_at"),
            data.get("member_id"),
            data.get("image_path"),
        ))
    else:
        c.execute("""
            UPDATE stories SET title=?, content=?, author=?, created_at=?, member_id=?, image_path=?
            WHERE id=?
        """, (
            data["title"],
            data["content"],
            data.get("author"),
            data.get("created_at"),
            data.get("member_id"),
            data.get("image_path"),
            story_id,
        ))
    conn.commit()
    new_id = c.lastrowid if story_id is None else story_id
    conn.close()
    return new_id


def delete_story(story_id):
    """删除故事"""
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM stories WHERE id=?", (story_id,))
    conn.commit()
    conn.close()

