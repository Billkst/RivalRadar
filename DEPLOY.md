# RivalRadar 部署指南

> **分阶段部署**(两步均已完成):
> - **Step 1:** 前端 Vercel + 后端 Render,先拿到可访问 URL。
> - **Step 2(v0.6.1.0 已完成):** 接入 **Supabase Postgres** 持久化(SQLite / Postgres 双方言,容器重启不丢数据),见文末「Step 2:Supabase Postgres(已完成)」。

## 架构(Step 1)

```
浏览器 ──► Vercel(前端静态站, Vite 构建)
              │  VITE_API_BASE = https://<render 后端域名>
              ▼  (HTTPS 跨域 + SSE)
          Render(后端 FastAPI, 常驻容器, 单 worker)
              │  Supabase Postgres 持久化(设 DATABASE_URL;未设则容器内 SQLite)
              ▼  出站
          Doubao(方舟 ark.cn-beijing) + Tavily/Exa + Supabase(ap-southeast)
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
   | `RIVALRADAR_DB` | `rivalradar.db` | render.yaml 已带(仅 DATABASE_URL 未设时生效) |
   | `DATABASE_URL` | Supabase **Session pooler** 连接串(端口 5432) | secret;**设了即切 Postgres 持久化**(见文末 Step 2);不设则回落容器内 SQLite |
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

- **持久化**:已接入 **Supabase Postgres**(设 `DATABASE_URL`,Step 2 完成)→ 容器重启 / 重部署后历史 run **不丢**。若未设 `DATABASE_URL`,回落容器内 SQLite(Render 免费档无持久盘,重启即清,仅适合现跑现看)。
- **冷启动**:免费档闲置 15 分钟休眠,下次访问 ~1 分钟唤醒。
- **单 worker**:取消/SSE 靠进程内注册表,**不要**加 `--workers>1` / gunicorn 多 worker。
- **POST /run 无鉴权 + 无限流**:公网暴露后任何人可触发真 LLM 调用烧配额。demo 期可接受;若担心,Render/Vercel 可加访问密码,或 Step 2 顺带加 token 校验(见 `TODOS.md`)。

---

## Step 2:Supabase Postgres(v0.6.1.0 已完成)

存储层已是 **SQLite / Supabase Postgres 双方言**:设 Render 的 `DATABASE_URL=postgres://` 即切 Postgres 持久化(容器重启不丢数据),不设则回落容器内 SQLite。改造全部收敛在 `storage/db.py` + `repository.py`(+ `api/deps.py` 连接生命周期);`psycopg[binary]` 懒加载——仅 PG 部署时 import,本地 SQLite / 单测不装。

**关键认知(把原计划的"连接池重写"砍掉了)**:实时管线的 worker 线程只做搜索 / LLM(网络 I/O),**所有 DB 写都在节点主线程串行**(回调只 emit + 锁内攒内存)。所以单连接 / run 串行写就安全,**不需要 `psycopg_pool` 连接池**——比原计划简单得多,也不动实时管线。

实际改造:
- `connect()` 按 `DATABASE_URL` 分流;`_PgConnection` 薄封装(`?`→`%s`、execute / executemany / commit / **失败即 rollback** / close)。
- 6 处 upsert 改标准 `ON CONFLICT`(SQLite ≥ 3.24 与 PG 一套 SQL 通吃,不按方言分叉);`AUTOINCREMENT`→`BIGSERIAL`(PG_SCHEMA 内联全列);`cursor.lastrowid`→`RETURNING id`;`ORDER BY rowid`→`fetched_at, id`(PG 无 rowid);`list_agent_skills` 位置访问改列名;`delete_run` 用显式 `_RUN_SCOPED_TABLES`(PG 无 `sqlite_master`/`PRAGMA`)。
- 连接:Supabase **Session pooler(端口 5432,IPv4)**——Render 免费档出站只有 IPv4,直连是 IPv6-only 连不上;`prepare_threshold=None` 兼容 pgBouncer。连接串带密码 → 只填进 Render Dashboard 的 `DATABASE_URL`,**绝不入库**。
- 验证:SQLite **402 单测全绿**(向后兼容零变化)+ `spikes/spike_supabase_crud.py` 真打 Supabase 9 段 CRUD + 事务污染恢复全 PASS;合并 main 后 Render 自动重建,线上 run 落 Supabase 已实测。

> **ship 前 /review 跨模型(Claude + Codex)抓到 1 个真 HIGH**:PG `autocommit=False` 下一条写失败会 abort 整条长生命周期事务 → 后续 `mark_run_failed` 也写不进 → run 卡死 "running"(SQLite 不污染)。修法:`_PgConnection.execute/executemany` 失败即 `rollback()` 再抛。happy-path 冒烟测不到,真 Supabase 故意造写失败验证恢复。
