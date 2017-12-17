FROM python:3.6-alpine3.6

ENV PYTHONUNBUFFERED=0

RUN apk add --no-cache gcc \
                       musl-dev \
                       postgresql-dev

# For using early releases of marvelous
RUN apk update && \
   apk upgrade && \
   apk add git

ADD requirements.txt /
RUN pip install -r requirements.txt

ADD ./manage.py /manage.py
ADD ./weeklypulls /weeklypulls

CMD [ "python", "./manage.py", "runserver", "0.0.0.0:8000"]
EXPOSE 8000
