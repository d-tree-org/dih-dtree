#!/bin/bash 
source <( printenv )

hm='/dih/backends'
echo $dih_user

function setup_nginx(){
    apt-get remove -y openjdk-11-jre-headless postgresql postgis && apt-get autoremove;
    mv $hm/conf/nginx.conf /etc/nginx/nginx.conf
    rm /etc/nginx/sites-enabled/*  /etc/nginx/sites-available/*
    mv $hm/conf/nginx-sample.conf /etc/nginx/sites-available/${domain_name}.conf
    mv $hm/conf/nginx-default.conf /etc/nginx/sites-available/default.conf

    ln -s /etc/nginx/sites-available/default.conf /etc/nginx/sites-enabled/default.conf
    sed -ri "s/\{domain_name\}/$domain_name/g" /etc/nginx/sites-available/*.conf

    mkdir -p /public
    echo "Karibu" >/public/index.html
    chmod +r /public/index.html

    find $hm/scripts \! -iname *nginx* -type f -delete
    rm -r $hm/conf
}


function setup_ssl(){
    [ -f $certs_folder/$domain_name/fullchain.pem ] \
    && [ ! -f /etc/nginx/sites-enabled/${domain_name}.conf ] \
    && openssl dhparam -out /etc/ssl/certs/dhparams.pem 4096 \
    && ln -s /etc/nginx/sites-available/${domain_name}.conf /etc/nginx/sites-enabled/${domain_name}.conf
}


function listen_for_reloading_signal(){
  echo 'waiting for reloading signals from letsencrypt'
  while read -r line ; do 
    [[ $line == "reload" ]] \
      &&  setup_ssl \
      && nginx -s reload;
   echo "receive $line"; done < <(nc -l -p 12345)
}




function start(){
    echo 'nginx_set'|nc -q 1 dih-letsencrypt 12345 
    listen_for_reloading_signal &
    echo 'nginx is set'
    echo "#!/bin/bash
        nginx -g 'daemon off;'
        " > $hm/scripts/start_nginx.sh \
        && chmod u+x $hm/scripts/start_nginx.sh  \
        && nginx -g 'daemon off;'
}


setup_nginx \
&& start