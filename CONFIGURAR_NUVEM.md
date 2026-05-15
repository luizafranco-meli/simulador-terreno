# Como publicar o app e compartilhar cenários

## Passo 1 — Criar conta no Supabase (banco de dados gratuito)

1. Acesse https://supabase.com e crie uma conta gratuita
2. Clique em "New project" e dê um nome (ex: "simulador-terreno")
3. Anote a senha do banco — você precisará dela

## Passo 2 — Criar a tabela de cenários

Dentro do projeto Supabase, vá em **SQL Editor** e execute:

```sql
CREATE TABLE cenarios (
  nome TEXT PRIMARY KEY,
  dados JSONB NOT NULL,
  atualizado_em TIMESTAMPTZ DEFAULT NOW()
);
```

## Passo 3 — Pegar as credenciais

Vá em **Project Settings → API** e copie:
- **Project URL** (ex: https://xyzabc.supabase.co)
- **anon / public key** (chave longa que começa com "eyJ...")

## Passo 4 — Configurar localmente

Abra o arquivo `.streamlit/secrets.toml` e preencha:

```toml
[supabase]
url = "https://SEU-PROJETO.supabase.co"
key = "SUA-CHAVE-AQUI"
```

Reinicie o app com RODAR.bat — os cenários agora ficam na nuvem (ícone ☁️ na sidebar).

---

## Passo 5 — Publicar o app (para outras pessoas acessarem)

### 5a. Criar conta no GitHub
Acesse https://github.com e crie uma conta gratuita.

### 5b. Criar repositório e subir os arquivos
Faça upload de:
- app.py
- requirements.txt
- .streamlit/secrets.toml  ← NÃO suba este arquivo (contém credenciais)

> Crie um arquivo `.gitignore` com o conteúdo:
> ```
> .streamlit/secrets.toml
> cenarios_salvos.json
> ```

### 5c. Publicar no Streamlit Community Cloud
1. Acesse https://share.streamlit.io
2. Faça login com GitHub
3. Clique em "New app"
4. Selecione o repositório, branch (main) e arquivo (app.py)
5. Em "Advanced settings → Secrets", cole o conteúdo do secrets.toml
6. Clique em "Deploy"

Pronto! Em ~2 minutos você terá uma URL pública que qualquer pessoa pode acessar,
e todos os cenários salvos ficam compartilhados no Supabase.
