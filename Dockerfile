FROM ubuntu:24.04

ENV TZ=Europe/Oslo
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone
RUN apt-get update && apt-get install -y build-essential python3-dev python3-pip parallel

WORKDIR /app

COPY pyproject.toml .
RUN pip install . --break-system-packages

COPY models .
COPY detect.py .