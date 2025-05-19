FROM python:3.11-alpine3.18

ENV PYTHONUNBUFFERED=1

RUN apk add --no-cache gcc \
                       musl-dev \
                       postgresql-dev \
                       libmemcached-dev \
                       cyrus-sasl-dev \
                       zlib-dev \
                       git

RUN mkdir /app

WORKDIR /app

ADD requirements.txt /app/
RUN pip install -U pip
RUN pip install -r requirements.txt

ADD ./manage.py /app/manage.py
ADD ./weeklypulls /app/weeklypulls

COPY ./docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh
ENTRYPOINT ["/docker-entrypoint.sh"]

EXPOSE 8000
