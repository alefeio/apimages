# Apimg no mesmo Nginx que outros domínios (ex.: Methodus)

O Apimages **não substitui** nem edita os sites que já existem (`methodusexercicios.com.br`, `methoduscursosonline.com.br`, etc.). Só entra **mais um** ficheiro de site.

## O que o Apimg adiciona

1. **Ficheiro próprio** em `sites-available/apimg.com.br` + link em `sites-enabled/` — contém **apenas** `server_name apimg.com.br` e `www.apimg.com.br`.
2. **Docker** escuta em **`127.0.0.1:8000`** (só dentro do servidor). O Nginx de `apimg.com.br` faz `proxy_pass` para esse endereço.
3. **Certificado Let’s Encrypt** separado em `/etc/letsencrypt/live/apimg.com.br/` — não remove certificados de outros domínios.

Nada disso altera `server_name` nem `proxy_pass` dos outros ficheiros em `sites-enabled`.

## O que **não** deve fazer ao instalar o Apimg

- **Não** apagar nem editar `apis.methodusexercicios.com.br`, `methoduscursosonline`, etc.
- **Não** usar `default_server` no bloco do `apimg.com.br` (o exemplo do projeto **não** usa).
- **Não** rodar `rm sites-enabled/default` se o servidor ainda precisar desse fallback — só remova `default` se souber que nada depende dele.

## Avisos `conflicting server name` (api.methodusexercicios…)

Esses avisos vêm de **vários ficheiros no mesmo servidor** declararem o **mesmo** `server_name` (por exemplo o site ativo + ficheiros `.bak` também dentro de `sites-enabled`). Isso é **independente** do Apimg: o `apimg.com.br` não entra nessa lista.

- Os sites Methodus **podem continuar como estão**; não é obrigatório mover `.bak` para o Apimg funcionar.
- O Apimg já responde pelo **Host** `apimg.com.br`; o Nginx escolhe o bloco pelo cabeçalho `Host` da requisição.

## Conflito de porta (raro)

Se **outro** serviço no mesmo Droplet já usar **`127.0.0.1:8000`**, altere no `docker-compose.prod.yml` a porta do host, por exemplo `"127.0.0.1:8001:8000"`, e no ficheiro Nginx do apimg troque `proxy_pass` / `upstream` para `127.0.0.1:8001`.

## Resumo

| Item                         | Apimg usa              | Outros domínios      |
|-----------------------------|------------------------|----------------------|
| `server_name`               | só `apimg.com.br`      | inalterados          |
| TLS                         | cert próprio           | certs próprios       |
| Backend                     | `127.0.0.1:8000` (API) | os que já configurou |

Pode manter **todos** os registros e ficheiros ativos do Methodus; o Apimg convive só como **mais um** virtual host.
