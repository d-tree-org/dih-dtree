#!/bin/bash

base='/dih/backends'
function setup_postgresql(){
    apt-get remove --purge -y  openjdk-11-jre-headless nginx && apt-get autoremove -y;
    pg_version=$(pg_lsclusters| grep -v missing | grep -Eo '^[0-9]*'|head -1)
    sed -ir "s/{version}/$pg_version/g" $base/conf/postgresql.conf 
    mv $base/conf/postgresql.conf /etc/postgresql/$pg_version/main/postgresql.conf
    chown postgres -R /var/lib/postgresql/
    chmod +r  /etc/postgresql/$pg_version/main/postgresql.conf
    echo 'host    all    all    172.10.0.0/16    md5' >> /etc/postgresql/$pg_version/main/pg_hba.conf
    pg_ctlcluster $pg_version main start
    rm -r $base/conf
    echo 'finished setup postgresql server' >> /dih/common/report_setup_done.log;
}


function update_admin_password(){
    [[ -z $dhis_admin_password ]] && return;

    runuser -u postgres -- psql dhis2 <<- SQL 
    --creating another schema since dhis2.public function "gen_random_uuid" has conflicts with pgcrypto;
    CREATE SCHEMA functions;
    SET search_path TO functions;
    CREATE EXTENSION IF NOT EXISTS pgcrypto;
    SET search_path TO public;
    UPDATE users
    SET password = functions.crypt('$dhis_admin_password', functions.gen_salt('bf'))
    WHERE username = 'admin';
SQL
    unset dhis_admin_password
}


function import_database(){
    echo 'looking for backup file';
    [ ! -f /data/.backup/dhis2.backup.sql ] && return;
    echo 'file found now executing the queries';
    runuser -u postgres -- psql dhis2 < /data/.backup/dhis2.backup.sql \
    && update_admin_password 
}


function setup_dhis2_db(){
    cd /var/lib/postgresql/
    runuser -u postgres -- psql << SQL  \
    && import_database \
    && echo 'dhis2_database_set'|nc -q 1 ${proj}-dhis 12345 \
    && listen_change_password_request &
        create user dhis with password '$dhis_password';
        create database dhis2;
        grant all on database dhis2 to dhis;
        \c dhis2
        create extension if not exists postgis; 
        create extension if not exists btree_gin; 
        create extension if not exists pg_trgm; 
SQL
    unset dhis_password;
}


function listen_change_password_request(){
  echo 'waiting to see if password change will be requested'
  while read -r line && [[ $line != "change" ]]; 
  do echo "receive $line"; done < <(nc -l -p 12345)
  update_admin_password
}


function start(){
    cat<<EOF \
    | sed -r 's/^\s*//g' >$base/scripts/start_postgres.sh \
    && chmod u+x $base/scripts/start_postgres.sh\
    && tail -f /dih/common/report_setup_done.log
        #!/bin/bash
        pg_version=$(pg_lsclusters| grep -v missing | grep -Eo '^[0-9]*'|head -1);
        pg_ctlcluster $pg_version main start;
        tail -f /dih/common/report_setup_done.log
EOF
}


setup_postgresql \
&& setup_dhis2_db \
&& start