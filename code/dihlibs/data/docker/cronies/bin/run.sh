#!/bin/bash

source <(printenv | sed -r '/[A-Z]+=/d;s/^./export \0/')

cd /dih/cronies/${1//./\//}
echo running $1 &>> /dih/cronies/logs/cron.log 
dih "${@:2}" &>> /dih/cronies/logs/cron.log
