# Teaching Awards Data Platform

高等教育教学成果奖数据分析平台，包含 Vue 前端、Flask 后端、MySQL 数据库结构、数据抽取清洗脚本和省份原始资料。

## Project Layout

- `frontend/`：Vue 3 + Vite 前端应用。
- `backend/`：Flask API 服务和运行配置。
- `database/`：MySQL 表结构 SQL。
- `data-pipeline/`：PDF/Word/Excel 抽取、清洗、补字段和导入脚本。
- `data/`：原始资料、标准化数据和临时处理中间产物。
- `docs/`：项目文档和省份接入说明。

## Local Development

Frontend:

```powershell
cd "C:\Users\吴\Desktop\高等教育数据分析\website"
npm run install:frontend
npm run dev
```

也可以直接进入真实前端目录启动：

```powershell
cd "C:\Users\吴\Desktop\高等教育数据分析\website\frontend"
npm run dev
```

不要再使用旧路径 `website\award-frontend`，整理后真实前端目录是 `website\frontend`。

Backend:

```powershell
cd "C:\Users\吴\Desktop\高等教育数据分析\website\backend"
$env:DEEPSEEK_API_KEY="你的真实 DeepSeek API Key"
python app.py
```

默认前端端口为 `5173`，后端端口为 `5000`。

`data/raw/`、`data/interim/`、`runtime/` 和 `data-pipeline/work/` 默认不提交到 GitHub；它们用于本地追溯、调试和处理中间结果。
