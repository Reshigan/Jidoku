FROM python:3.12-slim
WORKDIR /app
COPY packages ./packages
COPY services/api ./services/api
RUN pip install -e packages/jidoka-core -e packages/jidoka-adapters -e services/api
CMD ["uvicorn","jidoka_api.main:app","--host","0.0.0.0","--port","8080","--app-dir","services/api/src"]
