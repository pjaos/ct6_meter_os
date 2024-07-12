#!/bin/bash

pe=$(poetry env info -p)
if [ -n "$pe" ]; then
  echo "Removing $pe"
  rm -rf $pe
fi

date
poetry lock
poetry install
date