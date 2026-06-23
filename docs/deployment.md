# Deployment Notes

This project is currently deployed on an Alibaba Cloud ECS instance.

## Runtime

- OS: Ubuntu 22.04
- Web server: Nginx
- Backend: Flask + Gunicorn
- Database: MySQL
- Frontend: Vue/Vite static build

Current public test URL:

```text
http://8.148.236.195
```

## Server Layout

```text
/opt/teaching-awards-platform
├── backend/
├── frontend/
│   └── dist/
├── database/schema/
└── data/
```

Sensitive runtime configuration is stored outside the repository:

```text
/etc/teaching-awards.env
```

Example variables:

```env
DB_HOST=localhost
DB_USER=awards_user
DB_PASSWORD=replace_with_real_password
DB_NAME=teaching_awards

DEEPSEEK_API_KEY=replace_with_real_key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
```

Do not commit real passwords, API keys, `.env` files, or database dump files.

## Backend Service

The backend runs as a systemd service:

```bash
systemctl status teaching-awards-backend --no-pager
systemctl restart teaching-awards-backend
journalctl -u teaching-awards-backend -n 100 --no-pager
```

The service example is stored at:

```text
deployment/teaching-awards-backend.service.example
```

## Nginx

Nginx serves the frontend static files and proxies API requests to Gunicorn on `127.0.0.1:5000`.

Useful commands:

```bash
nginx -t
systemctl restart nginx
tail -n 100 /var/log/nginx/error.log
```

The Nginx example is stored at:

```text
deployment/nginx.conf.example
```

## Frontend Build

The ECS Node.js installation had package conflicts during the first deployment, so the frontend was built locally and uploaded to the server.

On Windows, from the project root:

```powershell
cmd.exe /c "set VITE_API_BASE=http://8.148.236.195&& npm.cmd --prefix frontend run build"
scp -r "C:\Users\吴\Desktop\高等教育数据分析\website\frontend\dist" root@8.148.236.195:/opt/teaching-awards-platform/frontend/
```

After uploading:

```bash
nginx -t
systemctl restart nginx
curl -I http://127.0.0.1
```

## Database Migration

Use `mysqldump` with `--result-file` and `--hex-blob` to avoid corrupting Chinese text and binary image data.

On Windows:

```powershell
mysqldump -u root -p --default-character-set=utf8mb4 --hex-blob --no-create-info --skip-triggers --result-file=teaching_awards_data_utf8.sql teaching_awards awards_master material_link_library wordcloud_images
scp "C:\Users\吴\Desktop\高等教育数据分析\website\teaching_awards_data_utf8.sql" root@8.148.236.195:/opt/teaching-awards-platform/teaching_awards_data_utf8.sql
```

On the server:

```bash
cd /opt/teaching-awards-platform
mysql -u awards_user -p teaching_awards -e "TRUNCATE TABLE awards_master; TRUNCATE TABLE material_link_library; TRUNCATE TABLE wordcloud_images;"
mysql -u awards_user -p --default-character-set=utf8mb4 teaching_awards < teaching_awards_data_utf8.sql
mysql -u awards_user -p teaching_awards -e "SELECT province, award_year, COUNT(*) AS total FROM awards_master GROUP BY province, award_year ORDER BY province, award_year;"
```

The Zhejiang CSV can be re-imported separately if it is not included in the local dump.

## Alibaba Cloud Security Group

Inbound rules needed for the current deployment:

- TCP `22`: SSH
- TCP `80`: HTTP

Do not expose:

- TCP `3306`: MySQL
- TCP `5000`: Flask/Gunicorn

## Domain And HTTPS

When a domain is ready:

1. Buy a domain from Alibaba Cloud or another registrar.
2. Complete ICP filing if the domain points to a mainland China server.
3. Add a DNS A record pointing the domain to `8.148.236.195`.
4. Update Nginx `server_name` from `_` to the domain.
5. Configure HTTPS after filing and DNS resolution are complete.
