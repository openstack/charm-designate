#!/usr/bin/make
LAYER_PATH := layers
INTERFACE_PATH := interfaces

clean:
	rm -Rf build

generate: clean
	LAYER_PATH=$(LAYER_PATH) INTERFACE_PATH=$(INTERFACE_PATH) tox -e generate
