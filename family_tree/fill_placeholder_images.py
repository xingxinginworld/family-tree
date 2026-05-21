#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CSV 图片占位填充工具 v1.0 — GUI 版

双击运行，选择 CSV 文件和占位图，点击「检查并替换」即可。
自动检查 CSV 最后一列（寸照路径）的图片是否存在，不存在的用占位图填充。
"""

import os
import sys
import csv
import shutil
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from datetime import datetime


# ══════════════════════════════════════════════════════════════════════
# 核心逻辑
# ══════════════════════════════════════════════════════════════════════


def detect_encoding(filepath):
    """自动检测文件编码（UTF-8 BOM > UTF-8 > GBK）"""
    with open(filepath, "rb") as f:
        raw = f.read()
    for enc in ("utf-8-sig", "utf-8", "gbk"):
        try:
            raw.decode(enc)
            return enc
        except:
            continue
    return "utf-8"


def process_csv(csv_path, placeholder_path, dry_run=False, callback=None):
    """
    核心处理函数
    - callback(status_text): 用于更新 UI 状态的回调
    返回 stats dict
    """
    stats = {"total": 0, "empty": 0, "exists": 0, "filled": 0, "failed": 0,
             "backup": "", "encoding": "", "details": []}

    def report(msg=""):
        if callback:
            callback(msg)

    # 1. 检测编码
    encoding = detect_encoding(csv_path)
    stats["encoding"] = encoding
    report(f"📄 编码检测：{encoding}")

    # 2. 读取 CSV
    with open(csv_path, "r", encoding=encoding, newline="") as f:
        reader = csv.reader(f)
        rows = list(reader)

    if not rows:
        report("❌ CSV 文件为空")
        return stats

    header = rows[0]
    data_rows = rows[1:]
    img_col_idx = len(header) - 1
    col_name = header[img_col_idx] if img_col_idx < len(header) else f"第{img_col_idx+1}列"
    stats["total"] = len(rows)

    report(f"📊 共 {len(data_rows)} 行数据，图片列：第{img_col_idx+1}列「{col_name}」")

    # 3. 备份
    if not dry_run:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base, ext = os.path.splitext(csv_path)
        backup_path = f"{base}_backup_{timestamp}{ext}"
        shutil.copy2(csv_path, backup_path)
        stats["backup"] = backup_path
        report(f"💾 已备份：{os.path.basename(backup_path)}")
    else:
        report("🔍 Dry-Run 模式（不会修改文件）")

    # 4. 检查占位图
    if not os.path.exists(placeholder_path):
        report(f"⚠️  占位图不存在：{placeholder_path}")
        if not dry_run:
            return stats  # 不继续
    else:
        report(f"✅ 占位图：{os.path.basename(placeholder_path)}")

    # 5. 逐行处理
    for i, row in enumerate(data_rows, start=2):
        img_path = row[img_col_idx].strip() if img_col_idx < len(row) else ""
        name = row[1].strip() if len(row) > 1 else f"第{i}行"

        if not img_path:
            stats["empty"] += 1
            continue

        if os.path.exists(img_path):
            stats["exists"] += 1
            continue

        if dry_run:
            stats["filled"] += 1
            stats["details"].append(("📋", i, name, img_path, "需填充"))
            continue

        try:
            dest_dir = os.path.dirname(img_path)
            if dest_dir and not os.path.exists(dest_dir):
                os.makedirs(dest_dir, exist_ok=True)
            shutil.copy2(placeholder_path, img_path)
            stats["filled"] += 1
            stats["details"].append(("✅", i, name, img_path, "已填充"))
        except Exception as e:
            stats["failed"] += 1
            stats["details"].append(("❌", i, name, img_path, f"失败：{e}"))

    # 6. 更新 CSV
    if not dry_run and stats["filled"] > 0:
        with open(csv_path, "w", encoding=encoding, newline="") as f:
            writer = csv.writer(f)
            writer.writerows(rows)
        report("✅ CSV 已更新")

    return stats


# ══════════════════════════════════════════════════════════════════════
# GUI 界面
# ══════════════════════════════════════════════════════════════════════


class PlaceholderApp:
    """CSV 图片占位填充工具 GUI"""

    def __init__(self, root):
        self.root = root
        self.root.title("CSV 图片占位填充工具 v1.0")
        self.root.geometry("680x520")
        self.root.minsize(620, 480)
        self.root.resizable(True, True)

        # 居中显示
        self.root.update_idletasks()
        w, h = 680, 520
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.root.geometry(f"{w}x{h}+{x}+{y}")

        self.csv_path = tk.StringVar()
        self.placeholder_path = tk.StringVar()
        self.dry_run = tk.BooleanVar(value=False)

        self._build_ui()

    # ── UI 构建 ────────────────────────────────────────────

    def _build_ui(self):
        # 主容器
        main = tk.Frame(self.root, padx=20, pady=16)
        main.pack(fill=tk.BOTH, expand=True)

        # ── 标题 ──
        title_lbl = tk.Label(
            main, text="🖼️  CSV 图片占位填充工具",
            font=("微软雅黑", 14, "bold"), fg="#2c3e50"
        )
        title_lbl.pack(anchor="w", pady=(0, 4))

        desc_lbl = tk.Label(
            main,
            text="检查 CSV 最后一列（寸照路径）的图片是否存在，不存在的用占位图填充",
            font=("微软雅黑", 9), fg="#666", wraplength=600, justify="left"
        )
        desc_lbl.pack(anchor="w", pady=(0, 14))

        # ── 文件选择 ──
        sep_cfg = {"fill": tk.X, "pady": 4}

        # CSV 文件
        csv_frame = tk.Frame(main)
        csv_frame.pack(**sep_cfg)
        tk.Label(csv_frame, text="CSV 文件：", font=("微软雅黑", 10),
                 width=10, anchor="e").pack(side=tk.LEFT)
        csv_entry = tk.Entry(csv_frame, textvariable=self.csv_path,
                             font=("微软雅黑", 9), fg="#555")
        csv_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 6))
        tk.Button(csv_frame, text="选择文件", font=("微软雅黑", 9),
                  command=self._select_csv,
                  bg="#3498db", fg="white", cursor="hand2",
                  width=8).pack(side=tk.RIGHT)

        # 占位图
        ph_frame = tk.Frame(main)
        ph_frame.pack(**sep_cfg)
        tk.Label(ph_frame, text="占位图：", font=("微软雅黑", 10),
                 width=10, anchor="e").pack(side=tk.LEFT)
        ph_entry = tk.Entry(ph_frame, textvariable=self.placeholder_path,
                            font=("微软雅黑", 9), fg="#555")
        ph_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 6))
        tk.Button(ph_frame, text="选择图片", font=("微软雅黑", 9),
                  command=self._select_placeholder,
                  bg="#3498db", fg="white", cursor="hand2",
                  width=8).pack(side=tk.RIGHT)

        # ── Dry-Run 选项 ──
        opt_frame = tk.Frame(main)
        opt_frame.pack(fill=tk.X, pady=(10, 2))
        tk.Checkbutton(
            opt_frame, text="Dry-Run 模式（仅检查，不修改任何文件）",
            variable=self.dry_run,
            font=("微软雅黑", 9), fg="#888"
        ).pack(anchor="w")

        # ── 执行按钮 ──
        btn_frame = tk.Frame(main)
        btn_frame.pack(fill=tk.X, pady=(6, 10))
        self.run_btn = tk.Button(
            btn_frame, text="▶  检查并替换", font=("微软雅黑", 12, "bold"),
            command=self._run,
            bg="#27ae60", fg="white", cursor="hand2",
            height=2, width=18
        )
        self.run_btn.pack()

        # ── 状态栏 ──
        self.status_lbl = tk.Label(
            main, text="就绪，请选择 CSV 文件和占位图",
            font=("微软雅黑", 9), fg="#888", anchor="w"
        )
        self.status_lbl.pack(fill=tk.X, pady=(0, 4))

        # ── 输出区 ──
        out_frame = tk.Frame(main)
        out_frame.pack(fill=tk.BOTH, expand=True)

        out_header = tk.Frame(out_frame)
        out_header.pack(fill=tk.X)
        tk.Label(out_header, text="处理报告", font=("微软雅黑", 10, "bold"),
                 fg="#2c3e50").pack(side=tk.LEFT)
        tk.Button(out_header, text="清空", font=("微软雅黑", 8),
                  command=self._clear_output,
                  bg="#95a5a6", fg="white", cursor="hand2",
                  width=5).pack(side=tk.RIGHT)

        txt_frame = tk.Frame(out_frame, bd=1, relief=tk.SUNKEN)
        txt_frame.pack(fill=tk.BOTH, expand=True, pady=(4, 0))

        sb = tk.Scrollbar(txt_frame)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        self.output_txt = tk.Text(
            txt_frame, font=("Consolas", 10), bg="#fafafa",
            fg="#333", wrap=tk.WORD, state=tk.DISABLED,
            yscrollcommand=sb.set, padx=6, pady=6
        )
        self.output_txt.pack(fill=tk.BOTH, expand=True)
        sb.config(command=self.output_txt.yview)

        # 快捷键
        self.root.bind("<Control-Return>", lambda e: self._run())

    # ── 文件选择 ────────────────────────────────────────────

    def _select_csv(self):
        path = filedialog.askopenfilename(
            title="选择家谱 CSV 文件",
            filetypes=[("CSV 文件", "*.csv"), ("所有文件", "*.*")]
        )
        if path:
            self.csv_path.set(path)

    def _select_placeholder(self):
        path = filedialog.askopenfilename(
            title="选择占位图",
            filetypes=[("图片文件", "*.jpg *.jpeg *.png *.bmp *.gif"),
                       ("所有文件", "*.*")]
        )
        if path:
            self.placeholder_path.set(path)

    # ── 输出 ────────────────────────────────────────────────

    def _append_output(self, text):
        """追加文本到输出区，自动换行"""
        self.output_txt.config(state=tk.NORMAL)
        self.output_txt.insert(tk.END, text + "\n")
        self.output_txt.see(tk.END)
        self.output_txt.config(state=tk.DISABLED)
        self.root.update_idletasks()

    def _clear_output(self):
        self.output_txt.config(state=tk.NORMAL)
        self.output_txt.delete("1.0", tk.END)
        self.output_txt.config(state=tk.DISABLED)
        self.status_lbl.config(text="已清空", fg="#888")

    def _update_status(self, text):
        """在状态栏和输出区同时显示"""
        self._append_output(text)
        self.status_lbl.config(text=text[:60], fg="#555")

    # ── 执行 ────────────────────────────────────────────────

    def _run(self):
        csv_path = self.csv_path.get().strip()
        placeholder_path = self.placeholder_path.get().strip()
        dry = self.dry_run.get()

        # 校验
        if not csv_path:
            messagebox.showwarning("提示", "请先选择 CSV 文件")
            return
        if not os.path.exists(csv_path):
            messagebox.showerror("错误", f"CSV 文件不存在：\n{csv_path}")
            return
        if not placeholder_path:
            messagebox.showwarning("提示", "请先选择占位图")
            return
        if not os.path.exists(placeholder_path) and not dry:
            ret = messagebox.askyesno("确认",
                f"占位图不存在：\n{placeholder_path}\n\n是否继续？")
            if not ret:
                return

        # 禁用按钮，防止重复点击
        self.run_btn.config(state=tk.DISABLED, text="⏳ 处理中...")
        self.root.update_idletasks()

        # 分隔线
        self._append_output("─" * 50)
        self._append_output(f"▶ 开始处理  {datetime.now().strftime('%H:%M:%S')}")
        self._append_output(f"  CSV：{os.path.basename(csv_path)}")
        self._append_output(f"  占位图：{os.path.basename(placeholder_path)}")
        self._append_output(f"  模式：{'Dry-Run' if dry else '正常'}")

        stats = None
        try:
            stats = process_csv(csv_path, placeholder_path,
                                dry_run=dry, callback=self._update_status)
        except Exception as e:
            self._append_output(f"❌ 出错：{e}")
            import traceback
            self._append_output(traceback.format_exc())

        # 恢复按钮
        self.run_btn.config(state=tk.NORMAL, text="▶  检查并替换")

        if stats is None:
            return

        # ── 输出汇总 ──
        self._append_output("─" * 50)
        self._append_output("📊 汇总")
        self._append_output(f"  总行数（含表头）：{stats['total']}")
        self._append_output(f"  路径为空（跳过）：{stats['empty']}")
        self._append_output(f"  图片已存在（跳过）：{stats['exists']}")
        self._append_output(f"  已填充占位图：{stats['filled']}")
        self._append_output(f"  失败：{stats['failed']}")
        if stats['backup']:
            self._append_output(f"  备份文件：{os.path.basename(stats['backup'])}")

        # 详情
        if stats["details"]:
            self._append_output(f"  详情（{len(stats['details'])} 项）：")
            for icon, row_num, name, img_path, msg in stats["details"]:
                name_short = name[:10] + "…" if len(name) > 10 else name
                self._append_output(f"    {icon} 第{row_num}行「{name_short}」 → {msg}")

        self._append_output(f"✔ 处理完成  {datetime.now().strftime('%H:%M:%S')}")
        self.status_lbl.config(
            text=f"✅ 完成：填充 {stats['filled']} 张",
            fg="#27ae60" if stats["details"] else "#888"
        )

        if stats["filled"] > 0 and not dry:
            messagebox.showinfo("完成",
                f"已填充 {stats['filled']} 张图片\n"
                f"失败 {stats['failed']} 张\n"
                f"备份文件：{os.path.basename(stats['backup'])}")


# ══════════════════════════════════════════════════════════════════════
# 入口
# ══════════════════════════════════════════════════════════════════════


def main():
    root = tk.Tk()
    app = PlaceholderApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
