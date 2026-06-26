# Themis

Themis 是面向 Dify `2.0.0-Beta2` workflow 的内部 AB Test 工具，用于对单一 workflow 变更后的历史样本进行回测、自动评估和人工偏好标注。

## 功能

- 创建对照组、实验组 A、可选实验组 B。
- 通过 JSON List 导入测试样本，并按输入 JSON Schema 校验。
- 后台逐条调用 Dify workflow，不做并发调用。
- Auto Eval 指标包括请求成功率、输出结构稳定性、响应时长统计。
- Preference Labeling 支持非盲评、单人单次标注和胜出版本统计。
- 账号使用 `app/env/users.json` 维护，密码按需求使用 MD5。
- 日志写入 `app/logs/system.jsonl` 和 `app/logs/experiments/{experiment_uuid}.jsonl`。

## 目录

- `app/backend`：FastAPI 后端。
- `app/frontend`：React + TypeScript + Ant Design 前端。
- `app/env`：环境配置与用户文件，本目录被 `.gitignore` 忽略。
- `app/sql/init_mysql.sql`：MySQL 初始化脚本。
- `crawler/app`：Dify Console 日志爬虫，用于生成 Themis 可导入的 JSON List 样本。
- `crawler/spec`：爬虫需求和技术规格。
- `test`：测试与烟测脚本，本目录被 `.gitignore` 忽略。
- `spec`：需求与 logo 归档，本目录被 `.gitignore` 忽略。

## 配置

复制配置样例：

```bash
cp app/env/config.example.json app/env/config.json
cp app/env/users.example.json app/env/users.json
```

`app/env/config.json` 字段：

- `DATABASE_URL`：MySQL SQLAlchemy 连接串。
- `DIFY_BASE_URL`：Dify API base URL，例如 `https://dify.example.com/v1`。
- `DIFY_TIMEOUT_SECONDS`：Dify 调用超时时间，默认 120 秒。
- `SESSION_SECRET`：预留会话密钥。
- `CORS_ORIGINS`：允许访问后端的前端地址。

创建或更新账号：

```bash
cd app/backend
python3 scripts/create_user.py --username admin --role admin
python3 scripts/create_user.py --username labeler --role labeler
```

上面的命令不带 `--password` 时会在终端提示输入密码，不会回显。也可以显式传入密码，适合初始化脚本：

```bash
python3 scripts/create_user.py --username admin --role admin --password your-admin-password
python3 scripts/create_user.py --username labeler --role labeler --password your-labeler-password
```

`app/env/users.example.json` 中的示例账号为：

- 管理员：`admin` / `admin`
- 标注员：`labeler` / `1234`

生产环境请创建新密码，或用上面的 CLI 覆盖示例账号。

## 数据库初始化

```bash
mysql -uroot -p < app/sql/init_mysql.sql
```

如果你使用自定义库名、用户或密码，请同步修改 `init_mysql.sql` 和 `app/env/config.json` 中的 `DATABASE_URL`。

## 本地启动

后端：

```bash
cd app/backend
python3 -m pip install -r requirements.txt
uvicorn themis.main:app --host 0.0.0.0 --port 8000
```

前端：

```bash
cd app/frontend
npm install
npm run dev
```

访问 `http://127.0.0.1:5173`。

## Dify 日志爬虫

爬虫用于从 Dify Console workflow 日志中提取开始节点输入，并生成 Themis 可直接导入的 JSON List。

准备配置：

```bash
cp crawler/app/config.example.json crawler/app/config.json
```

编辑 `crawler/app/config.json`：

```json
{
  "dify_base_url": "https://ai-dify.wenwen.top",
  "app_id": "67e672c4-eb26-431e-ab25-bbada762ce62",
  "authorization_bearer": "replace-with-dify-console-bearer-token",
  "dify_version": "2.0.0-beta-2",
  "status": "succeeded",
  "start_time": "2026-06-19T00:00:00+08:00",
  "end_time": "2026-06-26T23:59:59+08:00",
  "page_size": 50,
  "timezone": "Asia/Shanghai"
}
```

运行：

```bash
python3 -m crawler.app.cli --config crawler/app/config.json
```

也可以覆盖日期范围和状态：

```bash
python3 -m crawler.app.cli \
  --config crawler/app/config.json \
  --start 2026-06-19T00:00:00+08:00 \
  --end 2026-06-26T23:59:59+08:00 \
  --status succeeded
```

默认输出：

```text
crawler/output/{app_id}_{start}_{end}.json
crawler/output/{app_id}_{start}_{end}.errors.json
```

说明：

- 输出 JSON 文件可复制到 Themis 的导入数据 Modal 中。
- 样本按 `workId` 去重。
- 输出前会过滤 Dify 系统字段，例如 `sys.files`、`sys.user_id`、`sys.app_id`、`sys.workflow_id`、`sys.workflow_run_id`。
- 找不到开始节点输入、缺少 `workId`、重复 `workId` 的记录会写入 errors 文件。
- Bearer token 会过期；接口返回 `401` 时需要从 Dify Console 重新复制 token。

## 服务器部署（Nginx + Uvicorn）

以下示例假设：

- 项目目录：`/home/xueban/Themis`
- 前端访问地址：`http://服务器IP:8200`
- Nginx 监听端口：`8200`
- FastAPI 后端监听：`127.0.0.1:8000`
- 前端由 Nginx 托管 `app/frontend/dist`
- `/api/` 由 Nginx 反向代理到 FastAPI

### 1. 同步代码

```bash
scp -r app README.md xueban@server-ip:/home/xueban/Themis/
ssh xueban@server-ip
cd /home/xueban/Themis
```

如果服务器目录不同，用实际路径替换 `/home/xueban/Themis`。可以用下面命令确认绝对路径：

```bash
pwd
realpath app/frontend/dist
```

### 2. 准备配置

```bash
cp app/env/config.example.json app/env/config.json
cp app/env/users.example.json app/env/users.json
```

编辑 `app/env/config.json`：

```json
{
  "DATABASE_URL": "mysql+pymysql://tmk_qc:dHorLvVn@mr-l3uctca1046yao4sw6.rwlb.rds.aliyuncs.com:3306/tmk_qc?charset=utf8mb4",
  "DIFY_BASE_URL": "http://ai-dify.wenwen.top/v1",
  "DIFY_TIMEOUT_SECONDS": 120,
  "SESSION_SECRET": "replace-with-a-long-random-string",
  "CORS_ORIGINS": ["http://服务器IP:8200"]
}
```

说明：

- 本地测试 RDS host：`zhibanrds.rwlb.rds.aliyuncs.com`
- 服务器 RDS host：`mr-l3uctca1046yao4sw6.rwlb.rds.aliyuncs.com`
- 如果后续使用域名访问，`CORS_ORIGINS` 改成浏览器地址栏中的 origin，例如 `https://themis.example.com`。

### 3. 初始化数据库

```bash
mysql -uroot -p < app/sql/init_mysql.sql
```

如果数据库已经初始化过，可以跳过这一步。

### 4. 安装依赖并构建前端

```bash
cd /home/xueban/Themis/app/frontend
npm install
npm run build
ls -la dist
```

Nginx 的 `root` 必须指向 `dist` 的绝对路径。确认命令：

```bash
realpath dist
```

### 5. 配置 Nginx

确认 Nginx 已安装并运行：

```bash
nginx -v
systemctl status nginx
```

确认 `8200` 未被占用：

```bash
lsof -iTCP:8200 -sTCP:LISTEN -n -P
```

新建配置：

```bash
sudo vim /etc/nginx/conf.d/themis.conf
```

写入：

```nginx
server {
    listen 8200;
    server_name _;

    root /home/xueban/Themis/app/frontend/dist;
    index index.html;

    client_max_body_size 20m;

    location / {
        try_files $uri /index.html;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000/api/;
        proxy_http_version 1.1;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        proxy_connect_timeout 10s;
        proxy_send_timeout 180s;
        proxy_read_timeout 180s;
    }
}
```

如果你的项目不在 `/home/xueban/Themis`，把 `root` 改成 `realpath app/frontend/dist` 的输出。

检查并重载：

```bash
sudo nginx -t
sudo systemctl reload nginx
```

### 6. 启动后端

```bash
cd /home/xueban/Themis/app/backend
python3 -m pip install -r requirements.txt
mkdir -p ../logs
nohup uvicorn themis.main:app --host 127.0.0.1 --port 8000 > ../logs/backend.log 2>&1 &
echo $! > ../logs/backend.pid
```

查看后端日志：

```bash
tail -f /home/xueban/Themis/app/logs/backend.log
```

停止后端：

```bash
kill $(cat /home/xueban/Themis/app/logs/backend.pid)
```

重启后端：

```bash
cd /home/xueban/Themis/app/backend
kill $(cat ../logs/backend.pid)
nohup uvicorn themis.main:app --host 127.0.0.1 --port 8000 > ../logs/backend.log 2>&1 &
echo $! > ../logs/backend.pid
```

### 7. 验证部署

验证后端：

```bash
curl http://127.0.0.1:8000/api/health
```

期望返回：

```json
{"status":"ok","service":"themis"}
```

验证 Nginx API 反代：

```bash
curl http://127.0.0.1:8200/api/health
```

验证前端首页：

```bash
curl -I http://127.0.0.1:8200/
```

浏览器访问：

```text
http://服务器IP:8200
```

如果外网无法访问，检查云服务器安全组或防火墙是否放行 TCP `8200`。

### 8. 常见排查

查看 Nginx 配置是否正确：

```bash
sudo nginx -t
```

查看 Nginx 日志：

```bash
sudo tail -f /var/log/nginx/error.log
sudo tail -f /var/log/nginx/access.log
```

查看端口监听：

```bash
lsof -iTCP:8000 -sTCP:LISTEN -n -P
lsof -iTCP:8200 -sTCP:LISTEN -n -P
```

如果 `127.0.0.1:8000/api/health` 正常，但 `127.0.0.1:8200/api/health` 不正常，优先检查 Nginx `location /api/` 配置。

## 验证

```bash
python3 -m compileall app/backend
PYTHONPATH=app/backend pytest test
cd app/frontend && npm run lint
```
