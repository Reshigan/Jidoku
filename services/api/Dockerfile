# The governance kernel. Build context is the repo root (see docker-compose.yml, fly.toml) because
# services/api imports six sibling packages that live outside its own directory.
FROM python:3.12-slim

# Non-root. The kernel holds a hash-chained ledger on a mounted volume; a process that can rewrite
# its own image is a process that can rewrite the audit trail it is supposed to be evidence of.
RUN useradd --create-home --uid 10001 jidoka
WORKDIR /app

COPY packages ./packages
COPY services/api ./services/api

# Every package services/api imports, matching .github/workflows/ci.yml. A shorter list installs
# cleanly and then fails at import: jidoka_api.state imports jidoka_knowledge, the compiler router
# imports jidoka_compiler, and pip will not tell you until the first request.
RUN pip install --no-cache-dir \
      -e packages/jidoka-core \
      -e packages/jidoka-adapters \
      -e packages/jidoka-os \
      -e packages/jidoka-insight \
      -e packages/jidoka-knowledge \
      -e packages/jidoka-compiler \
      -e services/api \
 && mkdir -p /data && chown jidoka:jidoka /data

# Where the mounted volume lands. sqlite is the only store jidoka-core has (stdlib-only, by charter),
# so durability is a volume rather than a managed database — and that in turn means one machine, not
# a replica set. Two writers on one sqlite file is a corrupted ledger, not a scaling strategy.
ENV JIDOKA_DB_URL=sqlite:////data/jidoka.db \
    PYTHONUNBUFFERED=1

USER jidoka
EXPOSE 8080

# Single worker, deliberately. See the volume note above.
CMD ["uvicorn","jidoka_api.main:app","--host","0.0.0.0","--port","8080","--app-dir","services/api/src"]
