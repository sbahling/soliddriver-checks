#!/bin/bash

running_drivers=$(lsmod | awk 'NR>1 {print $1}')

result="{\"srcversions\":["
err_found=0
for driver in ${running_drivers};do
    d_srcver=$(/usr/sbin/modinfo ${driver} | grep srcversion | awk '{print $2}')
    srcver_file="/sys/module/${driver}/srcversion"
    if [ -f ${srcver_file} ]
    then
        f_srcver=$(cat ${srcver_file})
        if [ "${d_srcver}" != "${f_srcver}" ]
        then
            result="${result}{\"driver\":\"${driver}\",\"result\":\"mismatch\"},"
            err_found=1
        fi
    else
        result="${result}{\"driver\":\"${driver}\",\"result\":\"file not found\"},"
        err_found=1
    fi
done

if [ $err_found -eq 1 ] ; then
    # remove last ',' and add ']}' for json.
    result="${result::-1}]}"
else
    result="${result}]}"
fi

echo "${result}"
