# Apimages

API REST para hospedar **imagens e documentos**: o cliente faz **upload** com uma chave de API e recebe uma **URL pública** para usar em sites e apps (modelo parecido com o da Cloudinary, com armazenamento no próprio servidor).

## Funcionalidades

- `POST /v1/upload` — envio multipart; resposta com `url`, `public_id`, dimensões (só para imagens raster), formato e tamanho.
- `GET /i/{public_id}` — entrega do arquivo (sem autenticação, estilo CDN).
- Limite de tamanho configurável (`MAX_UPLOAD_BYTES`).

### Tipos aceitos (Content-Type)

| Categoria | MIME típico | Extensão |
|-----------|-------------|----------|
| Imagens | `image/jpeg`, `image/png`, `image/gif`, `image/webp`, `image/svg+xml` | .jpg, .png, .gif, .webp, .svg |
| PDF | `application/pdf` | .pdf |
| Word | `application/msword`, `application/vnd.openxmlformats-officedocument.wordprocessingml.document` | .doc, .docx |
| Excel | `application/vnd.ms-excel`, `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` | .xls, .xlsx |
| PowerPoint | `application/vnd.ms-powerpoint`, `application/vnd.openxmlformats-officedocument.presentationml.presentation` | .ppt, .pptx |
| RTF / texto | `application/rtf`, `text/csv`, `text/plain` | .rtf, .csv, .txt |
| OpenDocument | `application/vnd.oasis.opendocument.text` (e spreadsheet/presentation) | .odt, .ods, .odp |

O cliente deve enviar o **Content-Type** correto no campo `file` (navegadores e `curl -F file=@arq` costumam preencher automaticamente). Há checagem básica do conteúdo (PDF, ZIP para Office moderno/OpenDocument, assinatura OLE para .doc/.xls/.ppt, etc.).

### Otimização de imagens (raster)

- Se a **maior dimensão** (largura ou altura) passar de `IMAGE_MAX_EDGE_PX` (padrão **2560**), a imagem é **reduzida proporcionalmente** com filtro **LANCZOS** (boa qualidade para downscale na web).
- **JPEG**: qualidade alta (`IMAGE_JPEG_QUALITY`, padrão 90), `optimize`, progressive e subsampling 4:4:4 (`subsampling=0`) para evitar banding em degradês.
- **PNG / WebP**: PNG continua sem perda; WebP usa `IMAGE_WEBP_QUALITY` (padrão 92).
- **GIF estático**: paleta após redimensionamento; **GIF/WebP animado, MPO, APNG** etc.: o arquivo é **mantido como enviado** (sem quebrar animação ou vários quadros).
- Se **não** houver redimensionamento nem rotação EXIF, o **byte original** é guardado (evita recompressão JPEG desnecessária).
- Com rotação só por **EXIF**, o arquivo é regravado uma vez (orientação correta na web) com os mesmos critérios de qualidade acima.

Defina `IMAGE_MAX_EDGE_PX=0` para desligar só o redimensionamento.

## Desenvolvimento local

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
# Edite .env: defina API_KEY e, se quiser, BASE_URL
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Documentação interativa: [http://localhost:8000/docs](http://localhost:8000/docs)

### Upload (exemplo)

```bash
curl -X POST "http://localhost:8000/v1/upload" ^
  -H "X-API-Key: SUA_CHAVE" ^
  -F "file=@C:\caminho\foto.jpg"
```

A resposta JSON inclui `url`; abra essa URL no navegador para conferir.

## Variáveis de ambiente

| Variável | Descrição |
|----------|-----------|
| `BASE_URL` | URL pública da API (sem `/` no final). Usada para montar o campo `url` na resposta do upload. |
| `API_KEY` | Chave obrigatória para upload. |
| `STORAGE_PATH` | Diretório dos arquivos (padrão `./data/uploads`). |
| `MAX_UPLOAD_BYTES` | Tamanho máximo em bytes (padrão 10485760 = 10 MB). Aumente se precisar de PDFs ou planilhas grandes. |
| `IMAGE_MAX_EDGE_PX` | Maior lado permitido após otimização (padrão 2560). `0` desativa o redimensionamento. |
| `IMAGE_JPEG_QUALITY` | Qualidade JPEG ao regravar (1–100, padrão 90). |
| `IMAGE_WEBP_QUALITY` | Qualidade WebP ao regravar (1–100, padrão 92). |

Autenticação no upload: header `X-API-Key: <sua chave>` ou `Authorization: Bearer <sua chave>`.

## DigitalOcean (Droplet)

Guia completo (DNS, Droplet novo): **[docs/DEPLOY_DIGITALOCEAN.md](docs/DEPLOY_DIGITALOCEAN.md)**. **Só comandos no terminal do Droplet:** **[docs/SETUP_TERMINAL_DROPLET.md](docs/SETUP_TERMINAL_DROPLET.md)**. Exemplo Nginx: `deploy/nginx-apimg.conf.example`.

Resumo:

1. Droplet Ubuntu + firewall (80, 443, SSH).
2. Registro **A** de `apimg.com.br` (e opcionalmente `www`) para o IP do Droplet.
3. Docker + clone do repositório + `.env` com `BASE_URL=https://apimg.com.br` e `API_KEY=...`.
4. Nginx + `certbot --nginx` para HTTPS.
5. `docker compose -f docker-compose.prod.yml --env-file .env up -d --build` (API em `127.0.0.1:8000` atrás do Nginx).

### Docker local (desenvolvimento)

```bash
docker compose up -d --build
```

### Persistência

Use um volume ou disco anexo para `STORAGE_PATH`; sem isso, recriar o container apaga os arquivos.

### Escala / CDN (opcional)

Para algo mais próximo da Cloudinary em performance global, você pode depois enviar os uploads para **DigitalOcean Spaces** (compatível com S3) e devolver a URL do Space. Esta versão grava em disco local no servidor da API.

## Segurança

- Gere uma `API_KEY` longa e aleatória; não commite `.env`.
- Em produção, restrinja CORS em `app/main.py` se só alguns domínios forem usar a API.
- Considere rate limiting no Nginx ou um WAF para o endpoint de upload.
