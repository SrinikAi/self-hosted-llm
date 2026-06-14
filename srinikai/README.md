# SriniKai

A private, self-hosted LLM assistant. Frontend chat UI + FastAPI backend with
user accounts, persisted conversations, and a hardened model proxy. The model
itself runs locally via `llama-server` (llama.cpp).

```
Browser (webui)  ──►  SriniKai API (FastAPI)  ──►  llama-server (llama.cpp)
                      • accounts + JWT auth          • Gemma weights (local)
                      • SQL persistence
                      • hardened system prompt
                      • rate limiting / security
```

## Status

**Phase 1 — Foundation (done):**
- Email/password registration & login (argon2 hashing, JWT sessions)
- SQL persistence: users, conversations, messages (SQLite dev / Postgres prod)
- Authenticated streaming chat proxy to `llama-server` (SSE)
- Hardened **SriniKai** system prompt: concise, engaging, professional, never reveals identity
- Security layer: CORS allowlist, security headers, per-IP rate limiting, generic errors, no secret leakage

**Planned next phases:**
- Phase 2 — RAG / long-term memory (embeddings + pgvector retrieval; `Memory` model already in place)
- Phase 3 — MCP server + tool calling
- Phase 4 — Internet access tool (web search/fetch)
- Phase 5 — AWS deployment (RDS Postgres, ECS/Fargate, secrets, HTTPS)

## Run locally

1. **Start the model** (from the llama.cpp repo root):
   ```bash
   ./build/bin/llama-server -hf ggml-org/gemma-3-1b-it-GGUF --port 8080
   ```

2. **Start the API:**
   ```bash
   cd srinikai/backend
   python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt
   cp .env.example .env          # then set a strong JWT_SECRET
   ./.venv/bin/uvicorn app.main:app --reload --port 8000
   ```

3. **Open the UI:** `webui-simple/index.html` (point it at the API once the
   frontend is wired to auth in a follow-up).

API docs: http://localhost:8000/docs

## API

| Method | Path                                    | Auth | Purpose                         |
|--------|-----------------------------------------|------|---------------------------------|
| GET    | `/api/health`                           | no   | liveness                        |
| POST   | `/api/auth/register`                    | no   | create account → JWT            |
| POST   | `/api/auth/login`                       | no   | login → JWT                     |
| GET    | `/api/auth/me`                          | yes  | current user                    |
| POST   | `/api/chat`                             | yes  | streaming chat (SSE)            |
| GET    | `/api/conversations`                    | yes  | list user's conversations       |
| GET    | `/api/conversations/{id}/messages`      | yes  | messages in a conversation      |
| DELETE | `/api/conversations/{id}`               | yes  | delete a conversation           |

## Production (Postgres)

```bash
pip install -r requirements-postgres.txt
export DATABASE_URL="postgresql+psycopg://user:pass@your-rds:5432/srinikai"
export ENV=production
export JWT_SECRET="<48+ char random>"
```
On Postgres the `Memory.embedding` column uses native `pgvector`. Run
`CREATE EXTENSION IF NOT EXISTS vector;` on the database once.

## Security notes

- Passwords hashed with argon2; never stored or logged in plaintext.
- JWTs signed with `JWT_SECRET`; app refuses to boot in production with the default.
- Clients never reach `llama-server` directly — the proxy injects the system
  prompt and strips upstream model identifiers.
- CORS restricted to `CORS_ORIGINS`; strict security headers on every response.
- Rate limits on auth and chat endpoints; generic error messages resist
  account enumeration and internal-detail leakage.
