FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY gateway.py gateway_entrypoint.py costing.py tracing.py redis_backplane.py ./

EXPOSE 8080

CMD ["python", "gateway_entrypoint.py"]
