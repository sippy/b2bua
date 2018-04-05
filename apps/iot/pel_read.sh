# PROVIDE: pel_read
# REQUIRE: DAEMON
# BEFORE:  LOGIN
# KEYWORD: nojail shutdown

pel_read_enable="YES"
cli_arg="${1}"

. /etc/rc.subr

load_rc_config pel_read

unset pel_read_flags

name=pel_read
rcvar="${name}_enable"

command="/usr/local/bin/python3.6"
command_args="/home/sobomax/b2bua/apps/iot/pel_read.py -s /dev/cuau1 -n scrapegoat.sippysoft.com -u pel150 -P udv1pzs"
pidfile=/var/run/pel_read.pid

run_rc_command "$cli_arg"
