#!/bin/bash

# kernel modules under weak-updates should be a link to a kernel module,
# and that kernel module should be exist.
# Return:
# -- value: 1, pass
# -- value: 2, kernel module does not exist
# -- value: 3, kernel module under weak-updates should be a link, but it's a file!

files=$(find /lib/modules/*/weak-updates/ -regex ".*\.\(ko\|ko.xz\)$")

result="{\"weak-updates\":["

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
      result="${result}{\"km\":\"${line}\",\"status\":1},"
    else
      result="${result}{\"km\":\"${line}\",\"status\":2},"
    fi
  else
    result="${result}{\"km\":\"${line}\",\"status\":3},"
  fi
done
set +f
unset IFS

# remove last ',' and add ']}' for json.
result="${result::-1}]}"
echo "${result}"

