#!/bin/bash
what=$1
cmd=$2
source <( printenv|grep -v LS_COROR )

function create_run_command(){
    echo 'creating a cron runner'
    cat <<-RUN_FILE | sed -r 's/^\s+//g' > /dih/bin/run \
    && chmod +x /dih/bin/run && chown :dih /dih/bin/run 
        #!/bin/bash
        $(printenv | sed -r '/[A-Z]+=/d;s/^./export \0/')
        cd /dih/cronies/\${1//./\//}
        echo running \$1 >> /dih/cronies/logs/cron.log  2>&1
        ./run \$2 >> /dih/cronies/logs/cron.log  2>&1
RUN_FILE
echo user set
}


function install_apt_dependencies(){
    echo 'installing apt dependencies'
    regx='^\W*#\W*apt(-get)?\s*\K.*' 
    files=$(find /dih/cronies -maxdepth 3 -name run -type f -exec grep -lP $regx {} '+' | xargs )
    [ -z "$files" ] && return;
    grep -ohP $regx $files |
        sed -r 's/(install|update)//g; s/(^\s*|\s*$)//g; s/\s+/ /g' | sort -u | xargs apt-get install -y
    chmod ug+x $files 
    sed -i '/^\W+apt\W.*/d' $files
}


function setup_user(){
    echo 'setting up user'
   if id $dih_user >/dev/null 2>&1; then return 0; fi
   if [ -n $dih_user ] && [ ! -f /home/$dih_user ]; 
    then useradd -m -g dih $dih_user
        chmod  770 -R /dih && chown -R :dih /dih
        chown -R $dih_user:dih /home/$dih_user
        runuser -u $dih_user -- mkdir /home/$dih_user/.bin;
        ln -s /etc/cronies/config/ssh /home/$dih_user/.ssh
    #set links and references for containers to have the proper prefix based on project
   fi
}


setup_user \
&& create_run_command \
&& install_apt_dependencies && cron \
&& runuser -u $dih_user -- bash /dih/cronies/runuser.sh
