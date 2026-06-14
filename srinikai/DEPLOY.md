# Deploying SriniKai on AWS

This deploys the **API + Postgres**. The model (`llama-server`) is GPU/CPU heavy —
run it on a dedicated EC2 instance (GPU recommended) or swap `LLAMA_SERVER_URL`
for any OpenAI-compatible endpoint.

## Architecture

```
            Internet
               │  HTTPS
        ┌──────▼───────┐
        │ ALB (TLS via │   AWS Certificate Manager
        │ ACM cert)    │
        └──────┬───────┘
        ┌──────▼───────────┐        ┌─────────────────┐
        │ ECS Fargate      │  SQL   │ RDS Postgres    │
        │ srinikai-api     ├───────►│ + pgvector      │
        └──────┬───────────┘        └─────────────────┘
               │ HTTP (private)
        ┌──────▼───────────┐
        │ EC2 GPU instance │  llama-server (model weights)
        └──────────────────┘
   Frontend: S3 + CloudFront (static index.html)
   Secrets : AWS Secrets Manager (JWT_SECRET, DB creds)
```

## 0. Prerequisites
- AWS CLI configured, an ECR repo, a VPC with public+private subnets.

## 1. Build & push the image
```bash
cd srinikai/backend
aws ecr get-login-password --region us-east-1 \
  | docker login --username AWS --password-stdin <acct>.dkr.ecr.us-east-1.amazonaws.com
docker build -t srinikai-api .
docker tag srinikai-api:latest <acct>.dkr.ecr.us-east-1.amazonaws.com/srinikai-api:latest
docker push <acct>.dkr.ecr.us-east-1.amazonaws.com/srinikai-api:latest
```

## 2. RDS Postgres + pgvector
- Create an RDS PostgreSQL 16 instance (private subnet, SG allows 5432 from the API SG only).
- Connect once and enable the extension + index:
```sql
CREATE EXTENSION IF NOT EXISTS vector;
-- after first app boot (tables exist), add an ANN index for memory search:
CREATE INDEX IF NOT EXISTS memories_embedding_idx
  ON memories USING hnsw (embedding vector_cosine_ops);
```

## 3. Secrets (Secrets Manager)
```bash
aws secretsmanager create-secret --name srinikai/jwt --secret-string "$(python -c 'import secrets;print(secrets.token_urlsafe(48))')"
aws secretsmanager create-secret --name srinikai/db  --secret-string '{"url":"postgresql+psycopg://user:pass@<rds-host>:5432/srinikai"}'
```

## 4. ECS Fargate service
- Task definition: see `aws/ecs-task-def.json` (fill in `<acct>`, ARNs).
- Inject env from Secrets Manager: `JWT_SECRET`, `DATABASE_URL`.
- Set `ENV=production`, `CORS_ORIGINS=https://app.yourdomain.com`,
  `LLAMA_SERVER_URL=http://<model-ec2-private-ip>:8080`.
- Put the service behind an **ALB**; attach an **ACM** TLS cert (HTTPS only).
- App refuses to boot in production with a default `JWT_SECRET` — good.

## 5. Frontend (static)
```bash
# point the UI at your API, then upload
aws s3 sync srinikai/frontend s3://app.yourdomain.com/
```
Set the API base by editing `localStorage 'sk-api'`, or hardcode `const API=` in
`index.html` to `https://api.yourdomain.com`. Serve via CloudFront + ACM.

## 6. Model host (EC2)
- GPU instance (e.g. g5.xlarge). Install llama.cpp, run:
```bash
./llama-server -hf ggml-org/gemma-3-1b-it-GGUF --host 0.0.0.0 --port 8080
```
- SG: allow 8080 only from the ECS task SG (never public).
- For embeddings/RAG, run a second `llama-server --embeddings` and set `EMBEDDINGS_URL`.

## Security checklist
- [ ] HTTPS only (ALB + ACM); HSTS header is emitted in prod.
- [ ] DB and model SGs are private; no public 5432/8080.
- [ ] Secrets in Secrets Manager, never in the image or git.
- [ ] Rate limits tuned (`RATE_LIMIT_*`); consider AWS WAF on the ALB.
- [ ] Rotate `JWT_SECRET` via Secrets Manager rotation.
- [ ] Enable RDS encryption at rest + automated backups.
```
