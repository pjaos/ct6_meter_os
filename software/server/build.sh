#!/bin/bash
rm -rf picow 
cp -rf ../../picow .
rm -rf dist
poetry -vvv build
