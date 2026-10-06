.PHONY: all build_main clean pvc gen_listings

all: note.pdf
default: all

SHELL := /bin/bash
CUR_DIR := $(shell pwd)
DOCKER = docker run --rm \
	--user="$$(id -u):$$(id -g)" \
	--net=none \
	-v "$(CUR_DIR)/note:/tmp" \
	-w=/tmp \
	neitex:latex

# Если в будущем появится program/main.cpp -- раскомментируй
gen_listings:
	@true
#	[ -f program/main.cpp ] && cp program/main.cpp note/attachments/program.cpp || true

build_main: note/*.tex gen_listings
	$(DOCKER) latexmk \
		-pdflatex='pdflatex -shell-escape -interaction=nonstopmode -synctex=1 %O %S' \
		-pdf \
		note.tex

note.pdf: build_main
	cp note/note.pdf .

pvc:
	$(DOCKER) latexmk \
		-pdflatex='pdflatex -shell-escape -interaction=nonstopmode -synctex=1 %O %S' \
		-pvc -pdf \
		note.tex

clean:
	rm -f note.pdf
	$(DOCKER) latexmk -C