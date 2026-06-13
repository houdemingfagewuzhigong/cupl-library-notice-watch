# 法大图书馆通知公告观察站

[English README](README.md)

这是一个非官方的中国政法大学图书馆公开通知与服务信息每日归档项目，面向需要跟踪图书馆公告、资源服务、培训讲座和开放安排的学生、教师与数据分析学习者。

![看板示意](assets/demo.svg)

## 项目定位

- 目标站点：`https://lib.cupl.edu.cn/`
- 通知来源：图书馆官网首页及公告类公开链接
- 覆盖栏目：图书馆公开信息

当前环境访问该站点会返回“访问被限制”。爬虫使用 Playwright 浏览器上下文访问官网，并在可访问时抓取标题、链接、日期、栏目、来源页面和抓取时间；若被限制，则写入 `data/meta.json` 诊断信息，不伪造数据。

## 快速开始

```bash
pip install playwright
python -m playwright install chromium
python3 scraper.py 20
python3 -m http.server 8000
```

然后打开 `http://localhost:8000` 查看静态看板。

## 数据结构

- `data/notices.json`：合并后的历史公告。
- `data/notices.csv`：便于 Excel/WPS 打开的 CSV。
- `data/history/YYYY-MM-DD.json`：每天本次运行新抓到的数据。
- `data/meta.json`：更新时间、来源 URL、总量、诊断信息和免责声明。

每条公告字段包括 `id`、`title`、`date`、`url`、`summary`、`section`、`source_url`、`first_seen_at`、`last_seen_at`。

## 定时更新

`.github/workflows/update.yml` 会安装 Python、Node 和 Playwright Chromium，每天执行 `python3 scraper.py 20`，并在 `data/` 变化时自动提交。

## 前端看板

`index.html`、`styles.css`、`app.js` 构成一个可直接部署的静态看板，支持最新公告展示、关键词搜索、栏目筛选、统计卡片和 JSON/CSV 导出。

## 申报材料

`docs/project_proposal.docx` 是使用 `python-docx` 生成的项目说明/创新创业申报材料，包含项目背景、目标用户、技术路线、数据结构、合规说明、应用价值和后续扩展。

## 免责声明

本项目仅归档公开网页信息，不绕过访问控制，不抓取个人隐私数据，不代表中国政法大学官方。公告内容以学校官方页面为准。

## License

MIT
