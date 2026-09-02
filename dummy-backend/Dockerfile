FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

EXPOSE 8000

# Single worker on purpose: docker-compose caps each replica at cpus: "1.0", and
# one worker saturating one core is what lets /burn-cpu reliably push the
# observed CPU metric past the gateway's 80.0 burst threshold. More workers
# would spread the burn across cores and dilute the signal.
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
