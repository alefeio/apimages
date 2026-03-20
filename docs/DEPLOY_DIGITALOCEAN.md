# Deploy na DigitalOcean — apimg.com.br

Checklist na ordem que costuma evitar dor de cabeça (DNS + HTTPS).

## 1. Droplet

1. No painel da DigitalOcean: **Create → Droplets**.
2. **Image:** Ubuntu 22.04 ou 24.04 LTS.
3. **Plano:** o mais barato pode servir para começar; aumente se o tráfego/upload crescer.
4. **Região:** a mais próxima dos seus usuários (ex.: NYC ou São Francisco se o público for misto).
5. **Autenticação:** chave SSH (recomendado).
6. Crie o Droplet e anote o **IP público** (IPv4).

## 2. DNS no Registro.br (ou onde o domínio estiver)

Para `apimg.com.br` apontar para o Droplet:

| Tipo | Nome / Host | Dados / Valor | TTL |
|------|-------------|---------------|-----|
| **A** | `@` (ou em branco, conforme o painel) | `IP_DO_DROPLET` | 3600 |
| **A** | `www` (opcional) | `IP_DO_DROPLET` | 3600 |

- No Registro.br, após alterar DNS, a propagação pode levar de minutos a algumas horas.
- Antes do passo 6 (Certbot), o domínio **precisa** já resolver para o IP do Droplet.

## 3. Firewall no Droplet

Na DigitalOcean, em **Networking → Firewalls** (ou nas regras do Droplet), permita:

- **22** (SSH) — só do seu IP, se possível.
- **80** (HTTP) — para o Let’s Encrypt validar e redirecionar.
- **443** (HTTPS).

No servidor (opcional, `ufw`):

```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
```

## 4. Docker no Ubuntu

```bash
sudo apt update && sudo apt install -y ca-certificates curl git
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
# faça logout e login de novo para o grupo docker valer
```

(Compose v2 vem como `docker compose`.)

## 5. Código e variáveis

```bash
cd /opt
sudo git clone https://SEU_REPOSITORIO/Apimages.git apimages
sudo chown -R $USER:$USER /opt/apimages
cd /opt/apimages
```

Crie o `.env` (não commite):

```bash
nano .env
```

Conteúdo mínimo de produção:

```env
BASE_URL=https://apimg.com.br
API_KEY=<gere uma chave longa e aleatória>
MAX_UPLOAD_BYTES=20971520
```

Ajuste `MAX_UPLOAD_BYTES` ao que você quer permitir; o Nginx também precisa aceitar esse tamanho (veja o exemplo em `deploy/nginx-apimg.conf.example`).

Para subir **só na máquina local** (Nginx na frente), use `ports` amarrados ao loopback — veja a seção abaixo.

## 6. Nginx + HTTPS (Let’s Encrypt)

Instale Nginx e Certbot:

```bash
sudo apt install -y nginx certbot python3-certbot-nginx
```

Copie o exemplo (começa só em **HTTP** na porta 80; o Certbot inclui SSL depois):

```bash
sudo cp /opt/apimages/deploy/nginx-apimg.conf.example /etc/nginx/sites-available/apimg.com.br
sudo ln -sf /etc/nginx/sites-available/apimg.com.br /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
```

Obtenha o certificado **somente quando** `apimg.com.br` já resolver para o IP do Droplet:

```bash
sudo certbot --nginx -d apimg.com.br -d www.apimg.com.br
```

O Certbot edita o arquivo do site e passa a servir **HTTPS** com redirecionamento de HTTP. Renovação: automática (timer do `certbot`).

## 7. Subir a API com Docker

Na pasta do projeto (`.env` com `BASE_URL` e `API_KEY` já criado):

```bash
cd /opt/apimages
docker compose -f docker-compose.prod.yml --env-file .env up -d --build
```

A API fica só em **127.0.0.1:8000** (não exposta na internet direto). O Nginx encaminha `https://apimg.com.br` → `http://127.0.0.1:8000`.

Alternativa manual:

```bash
docker build -t apimages .
docker run -d --name apimages --restart unless-stopped \
  -p 127.0.0.1:8000:8000 \
  -v apimages_data:/data/uploads \
  --env-file .env \
  -e STORAGE_PATH=/data/uploads \
  apimages
```

## 8. Conferir

- `https://apimg.com.br/health` → JSON com `status: ok`.
- `https://apimg.com.br/docs` → Swagger.
- Upload de teste com `curl` e header `X-API-Key`; a `url` retornada deve começar com `https://apimg.com.br`.

## Próximos passos (recomendados)

- **Backup:** snapshot do Droplet ou backup periódico do volume `/data/uploads`.
- **CORS:** em `app/main.py`, restrinja `allow_origins` aos domínios que vão chamar a API.
- **Monitoramento:** UptimeRobot ou health check da DO no `/health`.
- **Escala:** mais tarde, Spaces + CDN se precisar de entrega global como a Cloudinary.
