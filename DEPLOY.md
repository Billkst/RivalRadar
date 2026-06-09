# RivalRadar 部署指南

> **分阶段部署**(按风险排序):
> - **Step 1(本文档,已就绪):** 前端 Vercel + 后端 Render(暂用 SQLite)。零存储层改动、不碰实时管线、401 测试不动 → 风险极低,先拿到可访问 URL。
> - **Step 2(后续):** SQLite → Supabase Postgres(连接池重写 + 方言适配),见文末「Step 2 路线」。

## 架构(Step 1)

```
浏览器 ──► Vercel(前端静态站, Vite 构建)
              │  VITE_API_BASE = https://<render 后端域名>
              ▼  (HTTPS 跨域 + SSE)
          Render(后端 FastAPI, 常驻容器, 单 worker)
              │  SQLite(容器内, 非持久; demo 现跑现看够用)
              ▼  出站
          Doubao(方舟 ark.cn-beijing) + Tavily/Exa
```

为什么后端不放 Vercel:单次调研是 5–7 分钟的长连 SSE,serverless 函数有执行时长上限会被掐断;必须常驻容器。

---

## 一、后端部署(Render)

仓库已含 `render.yaml` 蓝图(`python main.py`,读 `$PORT` 自动绑 `0.0.0.0`,健康检查 `/healthz`)。

1. 登录 https://render.com → **New +** → **Blueprint**(或 Web Service)→ 连接 GitHub 仓库 `Billkst/RivalRadar`,分支选部署分支。
   - 若用 Blueprint:Render 自动读 `render.yaml`。
   - 若手动建 Web Service:Runtime=Python,Build=`pip install -e .`,Start=`python main.py`,Health Check Path=`/healthz`,Region=**Singapore**(离 ark.cn-beijing 最近)。
2. **Environment** 里填 secrets(标 `sync:false` 的三项,绝不写进代码/仓库):
   | 变量 | 值 | 说明 |
   |---|---|---|
   | `ARK_API_KEY` | 你的方舟 key | secret |
   | `DOUBAO_MODEL` | endpoint ID | secret(与 key 同等敏感) |
   | `TAVILY_API_KEY` | 你的 Tavily key | secret(或 `EXA_API_KEY`) |
   | `ARK_BASE_URL` | `https://ark.cn-beijing.volces.com/api/v3` | render.yaml 已带 |
   | `RIVALRADAR_DB` | `rivalradar.db` | render.yaml 已带 |
   - `$PORT` 由 Render 注入,**不用手填**;`main.py` 已自动读取并绑 `0.0.0.0`。
3. Deploy。完成后拿到后端地址,如 `https://rivalradar-api.onrender.com`。
4. **验证后端**:浏览器开 `https://<后端>/healthz` 应返回 `{"ok": true}`。
   - 首次/闲置后访问有 ~1 分钟冷启动(免费档休眠),属正常。

> ⚠️ **跨境可达性自查**:Doubao 端点在北京。从 Render 海外节点出站访问 ark.cn-beijing 走公网直连(无需代理),Singapore 区延迟最低。部署后**务必真跑一次调研**确认 LLM 调用能通(若超时,多半是跨境延迟 → 已有 90s timeout 兜底,通常可过)。

---

## 二、前端部署(Vercel)

仓库 `frontend/vercel.json` 已配 SPA 回退(深链 `/run/:id` 不 404)。

1. 登录 https://vercel.com → **Add New → Project** → 导入 `Billkst/RivalRadar`。
2. **关键设置**:
   - **Root Directory** = `frontend`
   - Framework Preset = **Vite**(通常自动识别)
   - Build Command = `npm run build`(= `tsc -b && vite build`),Output = `dist`(默认)
3. **Environment Variables** 加一项:
   | 变量 | 值 |
   |---|---|
   | `VITE_API_BASE` | `https://<render 后端域名>`(**不带 `/api`、不带末尾斜杠**) |
   - 这是构建期注入;改了要 **Redeploy** 才生效。
4. Deploy。拿到前端地址,如 `https://rivalradar.vercel.app`。

> 为什么 `VITE_API_BASE` 不带 `/api`:本地 dev 走 vite 代理会剥掉 `/api` 前缀,后端真实路由是 `/run`、`/healthz` 这种无前缀的。生产前端直连后端根地址,`${VITE_API_BASE}/run` 才对得上。

---

## 三、联调验证 checklist

- [ ] `https://<后端>/healthz` 返回 `{"ok": true}`
- [ ] 打开 Vercel 前端,顶部不报「后端不可用」横幅(`ping /healthz` 通)
- [ ] 发起一次真实调研,实时工作台有事件流入(采集词/来源/矩阵逐格)
- [ ] 浏览器 DevTools Network 无 CORS 报错、无 Mixed Content(前端 HTTPS → 后端必须 HTTPS,Render 默认给 HTTPS)
- [ ] 调研跑完出报告 + 三色矩阵 + 决策;刷新页面能回放
- [ ] 后端 secrets 在 Render Dashboard,**不在仓库**(`git ls-files | grep -i env` 只应见 `.env.example`)

---

## 四、Step 1 已知限制(demo 可接受,提交材料如实标注)

- **SQLite 非持久**:Render 免费档无持久盘,容器重启/重部署后历史 run 清空。demo 是现跑现看,不影响;Step 2 上 Supabase 后持久化。
- **冷启动**:免费档闲置 15 分钟休眠,下次访问 ~1 分钟唤醒。
- **单 worker**:取消/SSE 靠进程内注册表,**不要**加 `--workers>1` / gunicorn 多 worker。
- **POST /run 无鉴权 + 无限流**:公网暴露后任何人可触发真 LLM 调用烧配额。demo 期可接受;若担心,Render/Vercel 可加访问密码,或 Step 2 顺带加 token 校验(见 `TODOS.md`)。

---

## Step 2 路线:SQLite → Supabase Postgres(后续稳做)

硬骨头不是 SQL 方言,是**连接线程安全**:实时管线把同一条连接传进线程池多线程并发写,SQLite 容忍、Postgres 禁止。所以 Step 2 = 引入 `psycopg_pool` 连接池 + 让后台 graph 任务每次写各借一条连接,而非共享一条。

已扫清的改造面(全部收敛在 `storage/db.py` + `repository.py` 两文件):
- `DATABASE_URL` 开关:未设→SQLite(本地+测试不变),设 `postgres://`→psycopg 分支。
- 88 处 `?`→`%s`;`INSERT OR REPLACE/IGNORE`→`ON CONFLICT`;`AUTOINCREMENT`→`BIGSERIAL`;`cursor.lastrowid`→`RETURNING id`;`ORDER BY rowid`→给 evidence 加序列列;删 `PRAGMA WAL`;PG 路径跳过老库在线迁移逻辑;行访问统一用列名(修 `list_agent_skills` 位置式访问)。
- Supabase 走 pooler(6543 transaction 模式)连接串 + `psycopg_pool.ConnectionPool`。
- 验证:401 测试仍在 SQLite 上跑通 + 真打一次 Postgres 调研验并发写。
