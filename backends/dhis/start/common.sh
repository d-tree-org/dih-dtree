#!/bin/bash


function setup_user(){
   if id $dih_user >/dev/null 2>&1; then return 0; fi
   if [ -n $dih_user ] && [ ! -f /home/$dih_user ]; 
    then useradd -m -g dih $dih_user
        chmod  770 -R /dih && chown  -R :dih /dih 
        chown -R $dih_user:dih /home/$dih_user

    #set links and references for containers to have the proper prefix based on project
     grep -rEl '\$\{proj\}' /dih | xargs  sed -ri "s/\\$\{proj\}/${proj}/g"
     grep -rEl '\$\{domain\}' /dih | xargs  sed -ri "s/\\$\{domain\}/${domain}/g"
   fi
}


function quiet (){
    "$@" > /dev/null 2>&1
     return $?
}

function trim(){
    sed -r 's/^\s*//g;s/\s*$//g' 
}



setup_user
