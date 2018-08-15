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
pidfile="/var/run/pel_read.pid"

command_args="/home/sobomax/b2bua/apps/iot/pel_read.py -s /dev/cuau1 -n 174.36.24.14 -u pel150_uac -P udv1pzs \
 -i ${pidfile}"

run_rc_command "$cli_arg"
