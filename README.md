# 绝区零 驱动盘评分助手

基于 AI 的 ZZZ 驱动盘评分工具，支持 OpenAI GPT-4o-mini 和 Claude API。

## 项目结构

```
zzz-disc-scorer/
├── app.py              # Flask 后端
├── requirements.txt    # 依赖
├── data/
│   └── characters.json # 角色数据库（可自行扩充）
└── templates/
    └── index.html      # 前端页面
```

## 本地运行

### 1. 安装依赖

```bash
cd D:\Desktop\zzz-disc-scorer
pip install -r requirements.txt
```

### 2. 配置 API Key

选择其中一个：

**Windows CMD：**
```cmd
set OPENAI_API_KEY=sk-xxxxxxxx
```

**Windows PowerShell：**
```powershell
$env:OPENAI_API_KEY="sk-xxxxxxxx"
```

**使用 Claude API：**
```cmd
set ANTHROPIC_API_KEY=sk-ant-xxxxxxxx
```

> 优先使用 OPENAI_API_KEY；若未设置则自动使用 ANTHROPIC_API_KEY。

### 3. 启动服务

```bash
python app.py
```

打开浏览器访问：http://localhost:5000

---

## 部署到 Render

1. 将项目推送到 GitHub 仓库
2. 在 [Render](https://render.com) 创建 Web Service
3. 配置：
   - **Build Command**：`pip install -r requirements.txt`
   - **Start Command**：`python app.py`
4. 在 Environment Variables 中添加 `OPENAI_API_KEY` 或 `ANTHROPIC_API_KEY`
5. 部署完成后获得公开 URL

## 部署到 Vercel（不推荐，Flask 需额外配置）

建议使用 Render 或 Railway。

---

## 扩充角色数据

编辑 `data/characters.json`，在 `characters` 数组中添加新角色，格式参考现有条目：

```json
{
  "id": "unique_id",
  "name": "角色名",
  "role": "主C/副C/辅助",
  "element": "属性",
  "recommended_sets": ["套装名1", "套装名2"],
  "set_notes": "套装选择说明",
  "main_stats": {
    "4": ["推荐主属性"],
    "5": ["推荐主属性"],
    "6": ["推荐主属性"]
  },
  "priority_substats": ["暴击率%", "暴击伤害%", "攻击力%"],
  "substat_notes": "副属性说明",
  "positioning": "角色定位详细说明"
}
```

---

## 修改 AI Prompt

在 `app.py` 的 `build_prompt()` 函数中修改评分规则和输出格式要求。
