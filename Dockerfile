FROM python:3.11-slim
WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir -r requirements.txt
ENV TZ=Asia/Jakarta
CMD ["python", "main.py"]
