.PHONY: setup install test clean run build lint

setup:
	$(MAKE) -C python setup

install:
	$(MAKE) -C python install

test:
	$(MAKE) -C python test

clean:
	$(MAKE) -C python clean

run:
	$(MAKE) -C python run

build:
	$(MAKE) -C python build

lint:
	$(MAKE) -C python lint
