# 家谱程序长时记忆

## 项目信息
- 名称：家谱制作工具（Family Tree Builder）
- 路径：d:/Project/编程相关/家谱程序制作-单文件版/
- 版本：v2.4
- 主入口：family_tree/main.py
- README已按开源标准重写（MIT协议）

## 代次规则（2026-04-17确认）
- 始祖（第一个创建的人）= generation 0（第0代）
- 子辈 = 父辈 generation + 1
- CSV导入模板需增加"代次"字段
- 代次冲突时（子<=父）导入失败并提示

## 优先级顺序
- P1：代次自动计算 ✅（2026-04-17完成）
- P2：故事摘要（A）✅（2026-04-17完成）
- P2：PDF打印（C）
- P2：照片墙拖拽排序+导出导入（D）
- P3：打印预览（E）

## 数据库表（当前）
- members：id/name/gender/birth_date/death_date/father_id/mother_id/spouse1_id/spouse2_id/bio/photo_path/extra_photos/generation/sort_order/x_pos/y_pos/created_at/spouse_id
- photo_wall：id/file_path/caption/member_id/sort_order/created_at
- stories：id/title/content/author/created_at/member_id/image_path

## 技术栈
- GUI: tkinter（Python内置）
- DB: sqlite3（Python内置）
- 图片: Pillow

## 开发约定
- 每个需求调试完毕后需用户确认，再进行下一个
- 计划文件：家谱程序TODO.md
- 工作记忆：.workbuddy/memory/YYYY-MM-DD.md

## v2.5-v2.6 新增
- io_print.py：HTML打印预览（封面/世系图/成员表/照片墙），浏览器Ctrl+P另存PDF
- 照片墙重写：拖拽排序列表视图 + 导出/导入顺序JSON
- sort_order 字段用于控制照片墙显示顺序，save_photo_order 更新顺序
