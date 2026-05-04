# Используем образ Python 3.14 как базовый
FROM python:3.14-slim AS base
WORKDIR /app
EXPOSE 6001

ENV FLASK_APP=DahuaHttpProxy/DahuaHttpProxy.py
ENV FLASK_ENV=production
ENV PYTHONUNBUFFERED=1
ENV FLASK_HOST=0.0.0.0
ENV FLASK_PORT=6001

# Копируем зависимости и устанавливаем их
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь проект в контейнер (сохраняя структуру папок)
COPY . .

ENTRYPOINT ["python", "DahuaHttpProxy/DahuaHttpProxy.py"]