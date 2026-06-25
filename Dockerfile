FROM python:3.12-alpine

WORKDIR /app

COPY . .

ENV DATA_DIR=/data
ENV PORT=80

VOLUME ["/data"]

EXPOSE 80

CMD ["python", "server.py"]
