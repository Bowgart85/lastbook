# Lastbook's browser server (server.py) for a home network: phones and tablets on the same Wi-Fi read the library
# from one computer. Keyword search only: no local AI model and no meaning-based search in this image.
#
#   docker compose -f packaging/docker/compose.yaml up -d --build
#
# The data folder (a downloaded pack: library-data/, derived/, pack.json) is mounted at /data and is written to:
# the access key (derived/lan-key), caches and saved items live there.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

# The same set the packaged Linux app uses (libzim, numpy, beautifulsoup4, pypdfium2).
COPY packaging/linux/requirements_linux.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY server.py assistant.py retrieval.py llm_local.py ./
COPY engine ./engine
COPY web ./web
COPY content ./content

EXPOSE 8890
# --lan: answer other devices, each needing the access link once. --no-index: no background semantic index.
CMD ["python", "-B", "server.py", "--lan", "--no-index", "--port", "8890", "--data", "/data"]
