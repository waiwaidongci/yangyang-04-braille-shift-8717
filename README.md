# 晨页盲文·双面压印班组试验

随机化单位是班组，按机型分层抽签，用班组均值做精确置换比较压印耗时，另看错点率护栏，归档试验放行建议。

## 模拟场景

[业务剧本](yangyang-business.md)记录模拟团队、上游观测、统计口径和交接去向。四个工作模块包括数据台账、分析任务、结果与复核、报表分发。工票和班组随机分派表从合成种子或 UTF-8 CSV 进入，两者谁先到都能收。分析员提交后，Python worker 对提交时固化的观测清单与分派表计算：先用分派表对账，缺班或分派冲突列入结果，对齐后按各机型原定的两组班数做单侧精确置换检验。晚到的工票和分派订正只进入新分析，失败重试沿用发起时的两份依据。负责人签核，随后可以下载结果或把报告定时投递到本地收件箱。2026-11-23 前的旧分析仍按原完全随机方法查看和重试。

## 启动

```sh
cp .env.example .env
docker compose up -d --build --wait
docker compose exec -T backend python -m scripts.seed_demo
```

浏览器打开 `http://127.0.0.1:18373`。API 健康检查位于 `http://127.0.0.1:19373/api/health`，数据库本地端口 `17873`。停机用 `docker compose down`。只有要重做演示数据时才加 `-v` 清除命名卷。

## 演示账号

| 角色 | 邮箱 | 演示密码 | 可执行动作 |
|---|---|---|---|
| 业务分析员 | `analyst@demo.local` | `Analyst-2026!` | 登记或导入样本、提交分析、下载内部结果 |
| 复核负责人 | `supervisor@demo.local` | `Supervisor-2026!` | 导入资料、签核或退回、安排或停止分发、查审计 |
| 只读查看 | `viewer@demo.local` | `Viewer-2026!` | 查看台账、已签核结果和本地收件箱 |

`.env` 以 `.env.example` 为模板。`FRONTEND_PORT`、`BACKEND_PORT`、`DB_PORT` 可做本机端口调整。Docker 私有子网可通过 `NETWORK_SUBNET` 覆盖。`JWT_SECRET` 和 `DB_PASSWORD` 为本地演示配置。`SEED_DEMO=false` 可跳过自动种子。所有公开端口绑定在回环地址。首次执行种子后，后续种子只填缺失观测，不覆盖已录入数据。

## 模块和本地开发

| 服务 | 技术 | 用途 |
|---|---|---|
| frontend | HTML、CSS、ES Modules、Nginx | 工作台、录入与报告 |
| backend | Python 3.12、FastAPI、SQLAlchemy | 校验、快照、业务 API 和 JWT |
| worker | Python 3.12、Redis | 计算排队、心跳和到时导出 |
| db | MySQL 8.0 | 观测、快照、签核、分发计划和审计 |
| redis | Redis 7 | 唤醒、心跳和登录限流 |

在 `backend` 中可用 `pip install -r requirements.txt` 安装本地依赖，设置 `DATABASE_URL`、`REDIS_URL` 和可写 `ARTIFACT_ROOT` 后运行 `uvicorn src.main:app --port 8000`，计算进程运行 `python -m src.worker`。前端修改在 `frontend/src`，用 `docker compose up -d --build frontend` 通过 Nginx 检查同源代理。业务输入定义在 `backend/src/domain/spec.json`，算法在同目录的 `analysis.py`（`analyze` 为旧完全随机口径，`analyze_stratified` 为现行机型分层口径）。角色、任务状态和签核状态在后端 `backend/src/constants/enums.py` 和前端 `frontend/src/constants/enums.js` 共同定义。数据库表在 `backend/src/models/workflow.py`。

分发计划锁定特定已签核快照，按北京时间显示。收件箱可下载真实 CSV，当前收件组是本地交接标签。停机跨过多个周期时补送最早未投递的一期，然后追到下一个将来的周期。新快照需重新签核并建新计划。

许可证为 [MIT](LICENSE)。
