FROM python:3.12-slim

WORKDIR /app
COPY . /app

RUN pip install --no-cache-dir -r requirements.txt
EXPOSE 6000

CMD ["flask", "--app", "src/box", "run", "--host=0.0.0.0", "--port=6000"]
