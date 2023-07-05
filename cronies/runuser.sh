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
    files=$(find /dih/cronies -name run -maxdepth 3  -type f -exec grep -lP $regx {} '+' | xargs )
    grep -ohP $regx $files |
        sed -r 's/(install|\-\-upgrade)//g; s/(^\s*|\s*$)//g; s/\s+/ /g' | sort -u |
        xargs pip install --upgrade pip 
    sed -ri 's/^\W*#\W*pip\W.*//g' $files
}

function install_cron(){
    mkdir -p /dih/cronies/logs
    touch $cron_log;
    regx='^\W*#\W*cron_time\s*\K.*';
    files=$(find /dih/cronies -name run -maxdepth 3 -type f -exec grep -lP $regx {} '+' | xargs )
    { 
        echo -e "SHELL=/bin/bash\nPATH=$PATH";
        grep -HoP $regx $files|  
            while IFS=':' read -r script cron; do 
                cmd=$(sed -E 's|/+|.|g;s|.+cronies.(.+).run|\1|g'<<<$script)
                echo "$cron run $cmd" ; done
    } | crontab -
    sed -ri 's/^\W*#\W*cron_time\W.*//g' $files
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

echo "configuration logs are $cron_log"
tail -f $cron_log || tail -f /dev/null