# Gunakan Python 3.11 agar lebih kompatibel dengan library terbaru
FROM python:3.11-slim

WORKDIR /app

# Set Timezone ke Jakarta
ENV TZ=Asia/Jakarta
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Install GIT (Wajib ada karena kita akan install pandas_ta dari Github)
RUN apt-get update && \
    apt-get install -y git && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

CMD ["python", "main.py"]
