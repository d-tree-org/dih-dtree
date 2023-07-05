#!/bin/bash

source common.sh
base='/dih'
function setup_postgresql(){
    apt-get install -y netcat postgresql postgis postgresql-contrib --fix-missing;
    pg_version=$(pg_lsclusters| grep -v missing | grep -Eo '^[0-9]*'|head -1)
    sed -ir "s/{version}/$pg_version/g" $base/conf/postgresql.conf 
    mv $base/conf/postgresql.conf /etc/postgresql/$pg_version/main/postgresql.conf
    chown postgres -R /var/lib/postgresql/
    chmod +r  /etc/postgresql/$pg_version/main/postgresql.conf
    echo 'host    all    all    172.10.0.0/16    md5' >> /etc/postgresql/$pg_version/main/pg_hba.conf
    rm -r $base/conf
}

start_postgres(){
    pg_version=$(pg_lsclusters| grep -v missing | grep -Eo '^[0-9]*'|head -1)
    status=$(pg_ctlcluster $pg_version main status)
    [[ $status == *"online" ]] \
    && pg_ctlcluster $pg_version main restart \
    || pg_ctlcluster $pg_version main start 
    
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
    backup_file=/data/.backup/db.sql.xz;
    echo "looking for backup file: $backup_file";
    [ ! -f $backup_file ] && echo 'backup file not found now proceeding..' && return;
    
    xz -d $backup_file && echo 'file found now executing the queries';
    runuser -u postgres -- psql dhis2 < /data/.backup/db.sql \
    && update_admin_password 
}


function setup_dhis2_db(){
    cd /var/lib/postgresql/
    runuser -u postgres -- psql << SQL  && import_database 
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
  echo 'Waiting to see if password change will be requested'
  while read -r line && [[ $line != "change" ]]; 
  do echo "receive $line"; done < <(nc -l -p 12345)
  update_admin_password
}


function start(){
    if [ -d $base/conf ] ; then 
        setup_postgresql && start_postgres  && setup_dhis2_db  \
        || { echo "failed to setup postgresql properly, will exit now " && return; }
    fi
    start_postgres
    echo 'postgress already started, notifying dhis2 container'
    echo 'dhis2_database_set' | nc -q 1 ${proj}-dhis 12345 
    tail -f /var/log/postgresql/postgresql-$pg_version-main.log
}
    
start || echo error postgress should not exit at this point;