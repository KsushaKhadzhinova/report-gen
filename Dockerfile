FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PLAYWRIGHT_BROWSERS_PATH=/opt/ms-playwright \
    REPORTGEN_HOME=/work/workspace \
    HOME=/home/app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        texlive-xetex \
        texlive-lang-cyrillic \
        texlive-latex-extra \
        texlive-fonts-recommended \
        fonts-liberation \
        fonts-dejavu-core \
        fontconfig \
        graphviz \
        plantuml \
    && fc-cache -f \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/report-gen
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install ".[capture]" \
    && playwright install --with-deps chromium \
    && chmod -R a+rX /opt/ms-playwright \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 1000 app \
    && mkdir -p /work \
    && chown app:app /work
USER app
WORKDIR /work

ENTRYPOINT ["report-gen"]
CMD ["--help"]
