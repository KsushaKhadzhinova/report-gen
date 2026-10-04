FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    REPORTGEN_HOME=/work/workspace

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
        git \
    && fc-cache -f \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/report-gen
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install ".[capture]" \
    && playwright install --with-deps chromium \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /work
ENTRYPOINT ["report-gen"]
CMD ["--help"]
