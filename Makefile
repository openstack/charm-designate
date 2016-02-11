#!/usr/bin/make
LAYER_PATH := layers

clean:
	rm -Rf build

generate: clean
	LAYER_PATH=$(LAYER_PATH) tox -e generate
