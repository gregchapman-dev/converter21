#!/bin/zsh
# Usage: abc2xml2abc file.abc
rm -r ./tmpxml
python converter21/abc/abc2xml.py -m 0 1000000 -o ./tmpxml $1
FILELIST=`ls ./tmpxml/*.xml`
FILELIST=($(echo "$FILELIST" | tr '\n' ' '))
python converter21/abc/xml2abc.py $FILELIST > $1.xml.abc
python -m musicdiff -o t -- $1 $1.xml.abc
