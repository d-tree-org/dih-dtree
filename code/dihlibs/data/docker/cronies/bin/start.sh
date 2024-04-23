#!/bin/bash
source /dih/bin/functions.sh

function launch() {
    cron_log="/dih/cronies/logs/cron.log"
    setup_user &&
        install_apt_dependencies &&
        quiet cron &&
        runuser -u doe -- bash <<-CODE
        source /dih/bin/functions.sh;
        should_initialize &&
            setup_python &&
            install_pip_dependencies &&
            set_logfile &&
            echo -e "configuration log file is $cron_log \\n\\nDone with setup you can now deploy" &&
            tail -f $cron_log || tail -f /dev/null;

CODE
}

function add_cron() {
    setup_user &&
        install_apt_dependencies &&
        runuser -u doe -- bash <<-CODE
        source /dih/bin/functions.sh;
            install_pip_dependencies &&
            install_cron
CODE
}

case $1 in
launch) launch ;;
add_cron) add_cron ;;
esac
