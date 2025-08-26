#!/bin/bash

source <(printenv | sed -r '/[A-Z]+=/d;s/^./export \0/')

cd /dih/cronies/${1//./\//}

last_arg="${args[-1]}" # the last element

if [ ! -d "$last_arg" ] && [[ ! "$last_arg" == *".zip.enc" ]]; then
    last_arg="$last_arg.zip.enc"
fi

echo running $1 &>> /dih/cronies/logs/cron.log
dih "${@:2:$(($#-2))}" "$last_arg" &>> /dih/cronies/logs/cron.log