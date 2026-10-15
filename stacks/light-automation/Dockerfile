FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY light_automation.py .

CMD ["python", "-u", "light_automation.py"]
