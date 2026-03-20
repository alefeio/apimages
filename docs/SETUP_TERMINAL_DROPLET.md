# Configurar no Droplet (terminal) — passo a passo

Para quem **já tem o Droplet** na DigitalOcean. No seu PC, conecte por SSH (troque o IP):

```bash
ssh root@IP_DO_DROPLET
```

*(Ou use outro usuário, ex.: `ssh ubuntu@IP` — depende da imagem do Droplet.)*

Se não usar SSH: no painel da DO, **Droplets → seu Droplet → Access → Launch Droplet Console**.

---

## 1) Firewall (se ainda não fez)

```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
```

Confirme nas regras da **DigitalOcean** (Firewall do Droplet) as portas **22, 80, 443**.

---

## 2) Docker + Git + Nginx + Certbot

```bash
sudo apt update && sudo apt install -y ca-certificates curl git nginx certbot python3-certbot-nginx
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
```

**Saia e entre de novo no SSH** (ou `newgrp docker`) para o grupo `docker` valer.

---

## 3) Colocar o projeto no servidor

**Opção A — repositório Git (recomendado):**

```bash
sudo mkdir -p /opt/apimages
sudo chown $USER:$USER /opt/apimages
cd /opt/apimages
git clone https://SEU_USUARIO/SEU_REPO.git .
```

**Opção B — sem Git:** no seu PC, na pasta do projeto:

`scp -r . root@IP_DO_DROPLET:/opt/apimages/`

Depois no servidor: `cd /opt/apimages`.

---

## 4) Arquivo `.env`

```bash
cd /opt/apimages
nano .env
```

Cole (ajuste `API_KEY`; use `openssl rand -hex 32` para gerar uma chave):

```env
BASE_URL=https://apimg.com.br
API_KEY=cole-uma-chave-longa-e-secreta-aqui
MAX_UPLOAD_BYTES=20971520
```

Salve: `Ctrl+O`, Enter, `Ctrl+X`.

**DNS:** `apimg.com.br` deve apontar (registro **A**) para este Droplet **antes** do Certbot no passo 6.

---

## 5) Nginx (proxy para a API)

**Servidor já com outros domínios:** só adicione o site do Apimg; **não** apague nem edite os ficheiros do Methodus/outros. Ver [deploy/NGINX_SERVIDOR_COMPARTILHADO.md](../deploy/NGINX_SERVIDOR_COMPARTILHADO.md).

```bash
sudo cp /opt/apimages/deploy/nginx-apimg.conf.example /etc/nginx/sites-available/apimg.com.br
sudo ln -sf /etc/nginx/sites-available/apimg.com.br /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

*(Remover `sites-enabled/default` só se tiver a certeza de que nenhum site depende dele — em servidores partilhados costuma deixar como está.)*

Se não usar `www`, edite o arquivo e remova `www.apimg.com.br` do `server_name` antes do `reload`.

---

## 6) HTTPS (Let’s Encrypt)

Só depois do domínio resolver para o IP do Droplet:

```bash
sudo certbot --nginx -d apimg.com.br -d www.apimg.com.br
```

(Sem `www`: `sudo certbot --nginx -d apimg.com.br`.)

---

## 7) Subir a API (Docker)

```bash
cd /opt/apimages
docker compose -f docker-compose.prod.yml --env-file .env up -d --build
```

Ver logs:

```bash
docker compose -f docker-compose.prod.yml logs -f
```

---

## 8) Testar

No navegador ou no seu PC:

- `https://apimg.com.br/health`
- `https://apimg.com.br/docs`

Upload (troque a chave e o caminho do arquivo):

```bash
curl -sS -X POST "https://apimg.com.br/v1/upload" \
  -H "X-API-Key: SUA_API_KEY" \
  -F "file=@/caminho/para/imagem.jpg"
```

---

## Atualizar o código depois

```bash
cd /opt/apimages
git pull
docker compose -f docker-compose.prod.yml --env-file .env up -d --build
```

---

## Certificado OK, mas “Could not install certificate”

O Let’s Encrypt já guardou o cert em `/etc/letsencrypt/live/apimg.com.br/`, mas o plugin **nginx** não encontrou um `server_name` igual ao domínio (site não criado, nome errado ou não está em `sites-enabled`).

1. Copie o exemplo **com HTTPS** (aponta para os ficheiros do certificado):

   ```bash
   cd ~/apimages/apimages
   git pull
   sudo cp deploy/nginx-apimg.https.conf.example /etc/nginx/sites-available/apimg.com.br
   sudo ln -sf /etc/nginx/sites-available/apimg.com.br /etc/nginx/sites-enabled/
   ```

2. Teste e recarregue:

   ```bash
   sudo nginx -t && sudo systemctl reload nginx
   ```

3. Se `nginx -t` falhar em **`ssl_dhparam`**, comente a linha `ssl_dhparam` no ficheiro **ou** gere o ficheiro (se existir `options-ssl-nginx.conf`, o `ssl_dhparams` às vezes falta):

   ```bash
   sudo openssl dhparam -out /etc/letsencrypt/ssl-dhparams.pem 2048
   ```

4. Opcional: `sudo certbot install --cert-name apimg.com.br` (depois do `server_name` correto).

**Instalação do Apimg não exige** remover links, certificados ou ficheiros de outros domínios no mesmo servidor. Avisos `conflicting server name` entre ficheiros **do mesmo** domínio (ex.: vários `.bak` com o mesmo `api.methodusexercicios…`) são à parte; o `apimg.com.br` usa `server_name` diferente e continua a funcionar.

---

Mais contexto (DNS, firewall na DO): [DEPLOY_DIGITALOCEAN.md](DEPLOY_DIGITALOCEAN.md). **Vários sites no mesmo Nginx:** [deploy/NGINX_SERVIDOR_COMPARTILHADO.md](../deploy/NGINX_SERVIDOR_COMPARTILHADO.md).
