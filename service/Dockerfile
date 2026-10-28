# Long-running worker process (persistent per-account TCP connections held
# in background threads — see app/main.py's docstring) — never deploy this
# as a serverless/scale-to-zero function, it needs to stay up continuously.

FROM python:3.14-slim

WORKDIR /app

# psycopg[binary] ships its own libpq, but build tooling is still needed for
# a couple of transitive wheels on slim images.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements.lock.txt ./
RUN pip install --no-cache-dir -r requirements.lock.txt

COPY . .

# The service does not need root at runtime. Keep /app writable for bounded
# admin debug captures while dropping Linux root privileges before Uvicorn.
RUN useradd --create-home --uid 10001 battlenode \
    && chown -R battlenode:battlenode /app
USER battlenode

# Real secrets (DATABASE_URL, WARPATH_ENCRYPTION_KEY, DEV_USER_EMAIL, the
# WARPATH_* SDK credentials) are supplied at `docker run`/compose time via
# --env-file or -e — never baked into the image. See .env.example.
EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
