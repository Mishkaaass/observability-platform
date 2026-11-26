# syntax=docker/dockerfile:1
FROM python:3.14-slim@sha256:22eafb370920ad8b429e0aec3fff433e0669968519f5d60469d83729c138b28b
# Same Debian security update baseline as the reviewed OpsBoard image.
RUN apt-get update \
    && apt-get install -y --no-install-recommends --only-upgrade \
       zlib1g apt libapt-pkg7.0 gzip libpcre2-8-0 libsqlite3-0 perl-base libzstd1 \
    && dpkg --compare-versions "$(dpkg-query -W -f='${Version}' apt)" ge 3.0.4 \
    && dpkg --compare-versions "$(dpkg-query -W -f='${Version}' libapt-pkg7.0)" ge 3.0.4 \
    && dpkg --compare-versions "$(dpkg-query -W -f='${Version}' libzstd1)" ge 1.5.7+dfsg-1+deb13u1 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
ARG GIT_SHA=local
ENV APP_GIT_SHA=${GIT_SHA}
COPY requirements.txt .
RUN python -m pip install --no-cache-dir -r requirements.txt \
    && python -m pip check \
    && python -m pip uninstall --yes pip
COPY app ./app
USER 10001:10001
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-server-header", "--no-access-log", "--no-proxy-headers"]
