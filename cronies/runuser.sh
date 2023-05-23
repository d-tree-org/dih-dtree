#!/bin/bash 
source <( printenv|grep -v LS_COROR )

cron_log=/dih/cronies/logs/cron.log;
function setup_python(){
    if which python>/dev/null; then return 0; fi
    cd /dih/lib
    tar -xvJf /dih/lib/python*.xz
    ln -s /dih/lib/python/bin/python3 /dih/bin/python
    ln -s /dih/lib/python/bin/pip3 /dih/bin/pip
}

function install_pip_dependencies(){
    pip --version
    regx='^\W*#\W*pip\s*\K.*' 
    files=$(find /dih/cronies -name run -maxdepth 2  -type f -exec grep -lP $regx {} '+' | xargs )
    grep -ohP $regx $files |
        sed -r 's/(install|\-\-upgrade)//g; s/(^\s*|\s*$)//g; s/\s+/ /g' | sort -u |
        xargs pip install --upgrade pip 
    sed -ri 's/^\W*#\W*pip\W.*//g' $files
}

function install_cron(){
    mkdir - /dhis/cronies/logs
    touch $cron_log;
    regx='^#cron_time\s*\K.*';
    files=$(find /dih/cronies -name run -maxdepth 2 -type f -exec grep -lP $regx {} '+' | xargs )
    { 
        echo -e "SHELL=/bin/bash\nPATH=$PATH";
        grep -HoP $regx $files|  
            while IFS=':' read -r script cron; do 
            dir="$(dirname $script)"
            echo "$cron run ${dir##*/}" ; done
    } | crontab -
    sed -ri 's/^#cron_time\W.*//g' $files
}

function should_initialize(){
    ! crontab -l >/dev/null \
    && ! which python \
    && ! which pip
}

should_initialize \
&& setup_python \
&& install_pip_dependencies \
&& install_cron

tail -f $cron_log
tail -f /dev/null