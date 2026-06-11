# 智能息肉诊疗辅助平台

本项目是一个面向结肠镜息肉辅助诊疗场景的毕业设计系统，围绕 BFNet 息肉分割模型构建完整的临床工作流。系统支持患者档案管理、结肠镜图像上传、息肉分割结果展示、LLM 医学分析、医生审核确认、报告下载以及患者病例文件管理。

## 项目功能

- 患者管理：维护患者基本信息、病史、过敏史、家族史和检查历史。
- 息肉分割：上传结肠镜图像后调用 BFNet 模型生成分割结果和息肉测量信息。
- 智能分析：结合息肉数量、大小、形态和患者信息，调用大语言模型生成医学分析建议。
- 医生审核：医生可编辑并确认最终报告，确认后支持导出 PDF。
- 病例报告：患者详情页支持上传 PDF、DOC、DOCX 等病例报告文件。
- 数据看板：展示患者数量、检查数量、高风险病例和待分析任务。

## 技术栈

| 模块 | 技术 |
| --- | --- |
| 前端 | React 18、TypeScript、Vite、Ant Design |
| 后端 | FastAPI、SQLAlchemy、Pydantic |
| 模型 | BFNet、PyTorch、OpenCV |
| 智能分析 | OpenAI 兼容接口、DeepSeek、SiliconFlow 等 |
| 存储 | SQLite/PostgreSQL、MinIO、本地文件存储 |
| 部署 | Docker Compose、本地开发脚本 |

## 目录结构

```text
polyp-ai-system/
├── backend/                 # FastAPI 后端服务
│   ├── app/
│   │   ├── api/v1/          # 患者、检查、分析等 API
│   │   ├── core/            # 配置与数据库初始化
│   │   ├── models/          # SQLAlchemy 数据模型
│   │   ├── schemas/         # Pydantic 数据结构
│   │   └── services/        # 模型、LLM、报告、存储服务
│   ├── main.py              # 后端入口
│   ├── requirements.txt     # Python 依赖
│   └── .env.example         # 环境变量模板
├── BFNet/                   # BFNet 模型代码
├── frontend/                # React 前端
├── docker-compose.yml       # Docker 编排
└── README.md
```

## 本地启动

### 1. 准备后端环境

```powershell
cd backend
copy .env.example .env
```

编辑 `backend/.env`，填写本机数据库、模型路径和 LLM API Key。真实密钥只保存在本地 `.env` 中，不要提交到 Git。

安装依赖：

```powershell
cd backend
pip install -r requirements.txt
```

启动后端：

```powershell
cd backend
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

健康检查地址：

```text
http://127.0.0.1:8000/health
```

### 2. 准备前端环境

```powershell
cd frontend
npm install
npm run dev -- --host 127.0.0.1 --port 3000
```

前端访问地址：

```text
http://127.0.0.1:3000
```

## 模型权重说明

模型权重文件较大，默认不提交到 GitHub。请将权重文件放到以下路径：

```text
BFNet/model/BFNet.pth
BFNet/pvt_v2_b2.pth
```

如需调整路径，可修改 `backend/.env` 中的：

```env
MODEL_PATH=../BFNet/model/BFNet.pth
MODEL_PVT_PATH=../BFNet/pvt_v2_b2.pth
```

## 环境变量说明

项目使用 `backend/.env` 管理本地配置。仓库只保留 `backend/.env.example` 作为模板，真实配置不上传。

常用配置项：

```env
DATABASE_URL=postgresql://<username>:<password>@localhost:5432/polyp_ai_db
OPENAI_API_KEY=<openai-api-key>
DEEPSEEK_API_KEY=<deepseek-api-key>
SILICONFLOW_API_KEY=<siliconflow-api-key>
MODEL_PATH=../BFNet/model/BFNet.pth
MODEL_PVT_PATH=../BFNet/pvt_v2_b2.pth
```

如果没有配置外部 LLM Key，系统仍可运行基础患者管理和图像分割流程，但智能医学分析能力会受限。

## Docker 启动

如需使用 Docker Compose：

```powershell
docker-compose up -d
```

常用命令：

```powershell
docker-compose ps
docker-compose logs -f backend
docker-compose logs -f frontend
docker-compose down
```

## 许可证

本项目使用仓库中的 `LICENSE` 文件作为许可证说明。

## 项目说明

本项目用于毕业设计和学习研究，不能替代医生诊断。系统生成的分析建议仅作为临床辅助参考，最终结论应由专业医生结合实际检查、病理结果和患者情况确认。
