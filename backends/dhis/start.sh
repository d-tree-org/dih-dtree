#!/bin/bash
what=$1
cmd=$2
xu="runuser -u $dih_user -- bash"



function setup_user(){
   if id $dih_user >/dev/null 2>&1; then return 0; fi
   if [ -n $dih_user ] && [ ! -f /home/$dih_user ]; 
    then useradd -m -g dih $dih_user
        chmod  770 -R /dih 
        runuser -u $dih_user -- mkdir /home/$dih_user/.bin;
        touch /dih/common/report_setup_done.log
        chown $dih_user:dih /dih/common/report_setup_done.log
        chown -R $dih_user:dih /home/$dih_user

    #set links and references for containers to have the proper prefix based on project
     grep -rEl '\$\{proj\}' /dih/backends | xargs  sed -ri "s/\\$\{proj\}/${proj}/g"
     grep -rEl '\$\{domain\}' /dih/backends | xargs  sed -ri "s/\\$\{domain\}/${domain}/g"
   fi
}


setup_user
case $what in
  server) bash "/dih/backends/scripts/start_${cmd}.sh" ;;
esac
tail -f /dev/null