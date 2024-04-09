FROM python:3.10
WORKDIR /usr/src/app
COPY . .

RUN apt-get update && \
    apt-get install -y git && \
    apt-get clean

RUN pip install --no-cache-dir -r requirements-dev.txt

# Dummy command to keep container running
CMD ["tail", "-f", "/dev/null"]