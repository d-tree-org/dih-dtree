#!/bin/bash 
source <( printenv )
source common.sh

conf='/dih/conf'
certs_dir="/dih/common/certs/letsencrypt/config/live/${domain_name}";

function setup_nginx(){
    if  ! quiet which nginx ; then 
        apt-get -y install nginx --fix-missing;
    fi

    nginx -g 'daemon off;' &

    quiet which nginx && [ -f /etc/nginx/sites-enabled/$domain_name.conf ] && return;
    rm /etc/nginx/sites-enabled/*  /etc/nginx/sites-available/*
    mv $conf/nginx.conf /etc/nginx/nginx.conf
    mv $conf/domain_name.conf /etc/nginx/sites-available/${domain_name}.conf
    rm -rf $conf
    sed -ri "s/\\$\{domain_name\}/$domain_name/g" /etc/nginx/sites-available/*.conf
    ln -s /etc/nginx/sites-available/$domain_name.conf /etc/nginx/sites-enabled/$domain_name.conf
    
    openssl dhparam --dsaparam -out /etc/ssl/certs/dhparams.pem 2048 
    mv /dih/start/letsencrypt.sh /dih/bin/renew && chmod +x /dih/bin/renew
    cron && runuser -u $dih_user -- renew  && setup_ssl
}


function setup_ssl(){
    [ ! -f $certs_dir/fullchain.pem ] && return; 
    echo "reloading nginx server"
    sed -ri 's/##//g' /etc/nginx/sites-enabled/$domain_name.conf
    nginx -s reload && echo " nginx x server reloaded successfull"
}


function listen_for_reloading_signal(){
    echo 'opening up to receive instructions from peers'
    while true; do
        while read -r line; do
            echo "received $line";
            case $line in
                reload)  setup_ssl ;;
            esac
         done < <(nc -l -p 12345)
    done
}



function start(){
    setup_nginx 
    listen_for_reloading_signal &
    tail -f /dev/null
}


start