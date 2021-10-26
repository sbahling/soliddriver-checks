#!/bin/bash

# drivers under weak-updates should be a link to a driver,
# and that driver should be exist.
files=$(find /lib/modules/*/weak-updates/ -regex ".*\.\(ko\|ko.xz\)$")

result="{\"weak-drivers\":["

if [[ ${files} == "" ]]
then
  echo "${result}]}"
  exit
fi

IFS='
'
set -f
for line in ${files}; do
  if [ -L ${line} ]
  then
    if [ -f ${line} ]
    then
      result="${result}{\"driver\":\"${line}\",\"result\":\"Pass\"},"
    else
      result="${result}{\"driver\":\"${line}\",\"result\":\"Driver does not exist!\"},"
    fi
  else
    result="${result}{\"driver\":\"${line}\",\"result\":\"Driver under weak-updates should be a link, but it's a file!\"},"
  fi
done
set +f
unset IFS

# remove last ',' and add ']}' for json.
result="${result::-1}]}"
echo "${result}"

