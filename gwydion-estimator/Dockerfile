# 327 Mb container
FROM python:3.10-slim-bullseye

ADD estimator.py mem_usage.csv cpu_usage.csv /

# Setup Python working environment
COPY requirements.txt .

# Upgrade pip
RUN pip install --upgrade pip

RUN pip install --no-cache-dir --upgrade -r requirements.txt

CMD [ "python", "./estimator.py"]
