FROM python:3.11-slim

WORKDIR /app

COPY api/main.py /app/api/main.py
COPY processor/vector_search.py /app/processor/vector_search.py
COPY db/init.sql /app/db/init.sql
COPY vector_index /app/vector_index

RUN pip install --no-cache-dir \
    fastapi \
    "uvicorn[standard]" \
    psycopg2-binary \
    redis \
    python-jose \
    faiss-cpu \
    pydantic

RUN pip install --no-cache-dir \
    torch \
    --index-url https://download.pytorch.org/whl/cpu

RUN pip install --no-cache-dir \
    sentence-transformers

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
