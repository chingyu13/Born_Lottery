FROM python:3.11-slim

WORKDIR /app

COPY server/requirements.txt /app/server/requirements.txt
RUN pip install --no-cache-dir -r /app/server/requirements.txt

# App needs data/ + public/ (poles served from Netlify in prod; public still useful locally)
COPY data /app/data
COPY public /app/public
COPY server/app.py /app/server/app.py

ENV HOST=0.0.0.0
ENV PORT=8765
EXPOSE 8765

CMD ["python", "/app/server/app.py"]
