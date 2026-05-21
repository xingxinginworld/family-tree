# 🪴 家谱制作工具 | Family Tree Builder

> 一款轻量、离线、隐私优先的桌面家谱制作工具。支持成员管理、世系图可视化、照片墙、CSV 导入导出及 HTML/PDF 导出输出。数据完全存储在本地，无网络依赖。

[English Below](#english-version)

---

## ✨ 功能特色 | Features

| 模块 | 功能 |
|------|------|
| 📋 **成员管理** | 添加/编辑/删除家庭成员，支持性别、出生/去世日期、配偶、父母关系 |
| 🌳 **世系图** | Canvas 绘制的树形图，节点含寸照，支持点击查看详情、放大缩小 |
| 🖼️ **照片墙** | 支持多选上传照片、编辑编号/说明/关联成员，支持按编号排序，支持导出/导入顺序 JSON |
| 📄 **数据导入导出** | CSV 批量导入导出，下载模板；HTML 整本输出（浏览器打印为 PDF） |
| 🔢 **代次自动计算** | 根据父母关系自动计算代数，支持手动指定代次 |
| 📖 **故事摘要** | 记录家族事迹、迁徙历史，支持关联成员或全局记录 |

---

## 🚀 快速开始 | Quick Start

### 环境要求 | Requirements

- Python 3.8+
- Pillow（图片处理）

### 安装 | Installation

```bash
# 克隆项目
git clone https://github.com/your-username/family-tree-builder.git
cd family-tree-builder

# 安装依赖
pip install Pillow

# 启动程序（两种方式均可）
python family_tree/main.py
# 或
python -m family_tree.main
```

> **首次运行**：`family_tree.db`（SQLite 数据库）和 `photos/`（照片目录）将自动创建。

---

## 📖 使用说明 | User Guide

### 界面布局

```
┌─────────────────────────────────────────────┐
│ 家谱制作工具          [+成员] [照片] [故事] [更多▼] │
├────────┬────────────────────────────────────┤
│ 成员列表 │  家谱树（点击节点查看详情）               │
│ 🔍 搜索 │  [刷新] [放大] [缩小] [收起]           │
│         │                                    │
│ 👤 成员  │    ┌───┐                           │
│         │    │祖父│← 第1代                     │
│         │  ┌─┴───┴─┐                          │
│         │  │父    │叔  ← 第2代                  │
│         │┌─┴─┐   └─┐                          │
│ [批量删除]││子 │   │   ← 第3代                  │
└────────┴────────────────────────────────────┘
```

### 代次规则 | Generation Rules

- **始祖** → generation = 1（第1代）
- 子女 → 父辈 generation + 1
- CSV 导入时若代次关系冲突（如子比父代数还小）则导入失败并提示

### 照片路径

- 程序接受**相对路径**（相对于程序根目录）或**绝对路径**
- 建议将照片放在 `photos/` 子目录下，使用相对路径方便迁移

---

## 🗂️ 项目结构 | Project Structure

```
family-tree-builder/
├── family_tree/
│   ├── __init__.py        # 包标识
│   ├── config.py          # 配置（数据库路径、照片目录）
│   ├── db.py              # 数据库初始化与连接
│   ├── models.py          # 数据模型 + CRUD 函数
│   ├── app.py             # 主窗口（核心框架 + 成员列表）
│   ├── ui_member.py       # 添加/编辑成员表单
│   ├── ui_tree.py         # 世系图绘制
│   ├── ui_photo_wall.py  # 照片墙
│   ├── io_csv.py          # CSV 导入/导出
│   ├── io_html.py         # HTML 导出（按世代分组）
│   ├── io_print.py        # 打印预览 HTML（浏览器 Ctrl+P 另存 PDF）
│   └── main.py            # 程序入口
├── photos/                # 照片存放目录
├── family_tree.db         # SQLite 数据库（自动生成）
├── 家谱程序TODO.md         # 功能路线图
└── README.md
```

---

## 🔧 开发指南 | Development

### 架构说明

- **GUI**：tkinter（Python 内置，无额外依赖）
- **数据库**：SQLite 3（Python 内置）
- **图片**：Pillow
- **无网络请求**，所有数据存储在本地 `family_tree.db`

### 数据库表结构

#### members（成员）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键，自增 |
| name | TEXT | 姓名（必填） |
| gender | TEXT | 'male' / 'female' |
| birth_date | TEXT | 出生日期 |
| death_date | TEXT | 去世日期（可空） |
| father_id | INTEGER | 父亲 ID（可空） |
| mother_id | INTEGER | 母亲 ID（可空） |
| spouse1_id | INTEGER | 配偶1 ID（可空） |
| spouse2_id | INTEGER | 配偶2 ID（可空） |
| bio | TEXT | 个人简介/备注 |
| photo_path | TEXT | 寸照路径 |
| extra_photos | TEXT | JSON 格式额外照片列表 |
| generation | INTEGER | 代次（1=始祖起） |
| sort_order | INTEGER | 同代排序序号 |

#### wall_photos（照片墙）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键，自增 |
| file_path | TEXT | 照片路径 |
| caption | TEXT | 说明文字 |
| member_id | INTEGER | 关联成员 ID（可空） |
| sort_order | INTEGER | 排序顺序（编号） |
| created_at | TEXT | 创建时间 |

#### stories（故事摘要）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键，自增 |
| title | TEXT | 标题（必填） |
| content | TEXT | 内容（必填） |
| author | TEXT | 记录人 |
| created_at | TEXT | 编制时间 |
| member_id | INTEGER | 关联成员 ID（可空，为全局记录） |
| image_path | TEXT | 配图路径（可空） |

### 运行测试

```bash
# 单元测试（数据库初始化）
python -c "from family_tree.db import init_db; init_db(); print('OK')"

# 模块导入测试
python -c "import family_tree.app; print('OK')"
```

---

## 🛣️ 路线图 | Roadmap

参见 [家谱程序TODO.md](./家谱程序TODO.md)，所有新增需求均记录于此。

---

## 📄 开源协议 | License

本项目基于 [MIT License](./LICENSE) 开源，欢迎 Fork、Star 和贡献。

---

---

## 🌐 English Version

### Family Tree Builder

A lightweight, offline-first desktop application for building and visualizing family trees.

**Key Features**:
- Member management with family relationships (father, mother, spouses)
- Interactive tree visualization with photos on nodes
- Photo wall with numbered ordering and per-photo editing
- CSV batch import/export, HTML full export
- Auto generation calculation from parent-child relationships
- Story summaries for family history

**Stack**: Python 3.8+ · tkinter · SQLite · Pillow

**Start**:
```bash
pip install Pillow
python family_tree/main.py
```

---

*Last Updated: 2026-05-21 | Version: v2.6f*
