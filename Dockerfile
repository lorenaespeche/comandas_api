FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ .

EXPOSE 4443

CMD ["hypercorn", "main:app", "--bind", "0.0.0.0:4443", "--certfile", "/cert/cert.pem", "--keyfile", "/cert/ecc-key.pem"]
