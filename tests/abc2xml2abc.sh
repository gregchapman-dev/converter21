#!/bin/zsh
# Usage: abc2xml2abc file.abc
python converter21/abc/abc2xml.py -m 1 1000000 -o ./tmpxml $1
python converter21/abc/xml2abc.py ./tmpxml/*.xml > $1.xml.abc
python -m musicdiff -o t -- $1 $1.xml.abc
