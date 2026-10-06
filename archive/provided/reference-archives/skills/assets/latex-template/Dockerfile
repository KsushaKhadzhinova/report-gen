# Taken from https://github.com/leplusorg/docker-latex
FROM debian:stable-slim

ARG USER_NAME=latex
ARG USER_HOME=/home/latex
ARG USER_ID=1000
ARG USER_GECOS=LaTeX

# hadolint ignore=DL3008
RUN apt-get update && \
  apt-get install --no-install-recommends -y adduser chktex ghostscript lacheck latexmk latex-make latex-mk texlive texlive-lang-cyrillic texlive-lang-english texlive-fonts-recommended texlive-science texlive-latex-extra texlive-pictures && \
  # Removing documentation packages *after* installing them is kind of hacky,
  # but it only adds some overhead while building the image.
  apt-get --purge remove -y .\*-doc$ && \
  # Remove more unnecessary stuff
  apt-get clean -y && \
  rm -rf /var/lib/apt/lists/*
COPY .docker_build/scalable-cyrfonts.deb /
RUN dpkg -i /scalable-cyrfonts.deb
RUN rm /scalable-cyrfonts.deb
COPY .docker_build/mtp2lite.deb /
RUN dpkg -i /mtp2lite.deb
RUN rm /mtp2lite.deb

RUN adduser \
  --home "${USER_HOME}" \
  --uid "${USER_ID}" \
  --gecos "${USER_GECOS}" \
  --disabled-password \
  "${USER_NAME}"
