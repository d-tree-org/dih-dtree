#!/bin/bash
what=$1
cmd=$2
source <( printenv|grep -v LS_COROR )

function create_runner(){
    echo 'creating a cron runner'
    cat <<-"SCRIPT" | sed -r 's/^\s*//g' > /dih/bin/run && chmod +x /dih/bin/run
        #!/bin/bash
        source <( printenv | grep -v LS_CO )
        cron_folder=$1
        cd /dih/cronies/$cron_folder
        ./run >> /dih/cronies/logs/cron.log  2>&1
SCRIPT

}


function install_apt_dependencies(){
    echo 'installing apt dependencies'
    regx='^\W*#\W*apt(-get)?\s*\K.*' 
    files=$(find /dih/cronies -maxdepth 2 -name run -type f -exec grep -lP $regx {} '+' | xargs )
    [ -z $files ] && return;
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
        chmod  770 -R /dih 
        runuser -u $dih_user -- mkdir /home/$dih_user/.bin;
        touch /dih/common/report_setup_done.log
        chown $dih_user:dih /dih/common/report_setup_done.log
        chown -R $dih_user:dih /home/$dih_user
        ln -s /dih/cronies/config/ssh /home/$dih_user/.ssh
        chmod  700 -R /home/$dih_user/.ssh
        chmod  600 /home/$dih_user/.ssh/*
        chmod  640 /home/$dih_user/.ssh/*.pub
    #set links and references for containers to have the proper prefix based on project
   fi
}

function start_cronies(){
    case $cmd in
        runner)
            find /dih/cronies/*  -type  d | grep -E '(letsencrypt)' |xargs rm -rf
            ;;
        letsencrypt)
            #careful this should be in a container of its owner, it removes other cronies
            find /dih/cronies/*  -type  d | grep -vE '(letsencrypt|\blogs\b)' |xargs rm -rf
            chown -R $dih_user:dih /dih/common/certs/letsencrypt ;;
    esac

    install_apt_dependencies && cron \
    && runuser -u $dih_user -- bash /dih/cronies/runuser.sh
}

setup_user \
&& create_runner \
&&  start_cronies 
