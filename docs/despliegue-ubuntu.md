# Despliegue en Ubuntu 24.04 (sin Docker)

Guía para instalar Odoo 18 Community con este módulo en un servidor Ubuntu 22.04 o 24.04.

## 1. Paquetes y PostgreSQL

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y git python3-venv python3-dev build-essential \
  libxml2-dev libxslt1-dev libldap2-dev libsasl2-dev libpq-dev \
  libjpeg-dev zlib1g-dev postgresql nginx
sudo -u postgres createuser --createdb odoo
```

Para los PDF, instala wkhtmltopdf 0.12.6 con parche de Qt (el paquete de `apt` no trae encabezados ni pies de página):
<https://github.com/wkhtmltopdf/packaging/releases>

## 2. Usuario y código

```bash
sudo adduser --system --group --home /opt/odoo odoo
sudo -u odoo git clone --depth 1 --branch 18.0 https://github.com/odoo/odoo.git /opt/odoo/odoo
sudo -u odoo git clone https://github.com/JavierYungaT/odoo18-quality-control.git /opt/odoo/custom
sudo -u odoo python3 -m venv /opt/odoo/venv
sudo -u odoo /opt/odoo/venv/bin/pip install -r /opt/odoo/odoo/requirements.txt
```

## 3. Configuración: `/etc/odoo.conf`

```ini
[options]
admin_passwd = <contraseña-maestra-larga>
db_user = odoo
addons_path = /opt/odoo/odoo/addons,/opt/odoo/custom/addons
data_dir = /opt/odoo/.local/share/Odoo
proxy_mode = True
workers = 4
max_cron_threads = 1
list_db = False
logfile = /var/log/odoo/odoo.log
```

```bash
sudo mkdir -p /var/log/odoo && sudo chown odoo: /var/log/odoo
sudo chown odoo: /etc/odoo.conf && sudo chmod 640 /etc/odoo.conf
```

## 4. Servicio systemd: `/etc/systemd/system/odoo.service`

```ini
[Unit]
Description=Odoo 18
After=network.target postgresql.service

[Service]
User=odoo
Group=odoo
ExecStart=/opt/odoo/venv/bin/python3 /opt/odoo/odoo/odoo-bin -c /etc/odoo.conf
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now odoo
journalctl -u odoo -f
```

## 5. Nginx y HTTPS

`/etc/nginx/sites-available/odoo`:

```nginx
upstream odoo { server 127.0.0.1:8069; }
upstream odoochat { server 127.0.0.1:8072; }

server {
    server_name erp.tudominio.com;
    client_max_body_size 50m;
    proxy_read_timeout 720s;

    location / {
        proxy_pass http://odoo;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    location /websocket {
        proxy_pass http://odoochat;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/odoo /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d erp.tudominio.com
```

## 6. Actualizar el módulo

```bash
cd /opt/odoo/custom && sudo -u odoo git pull
sudo systemctl stop odoo
sudo -u odoo /opt/odoo/venv/bin/python3 /opt/odoo/odoo/odoo-bin -c /etc/odoo.conf \
  -d <base> -u tk_quality_control --stop-after-init
sudo systemctl start odoo
```

## 7. Respaldos

```bash
# Base de datos (formato custom, comprimido)
sudo -u odoo pg_dump -Fc <base> > /backups/<base>-$(date +%F).dump
# Archivos adjuntos (filestore)
sudo tar czf /backups/filestore-$(date +%F).tar.gz -C /opt/odoo/.local/share/Odoo/filestore <base>
# Restaurar
sudo -u odoo createdb <base_restaurada>
sudo -u odoo pg_restore -d <base_restaurada> /backups/<base>-AAAA-MM-DD.dump
```
