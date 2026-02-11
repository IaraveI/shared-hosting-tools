#!/bin/bash
#
# List /home critical files modified during the last hour.
#
# VERSION       :0.5.1
# DATE          :2023-05-16
# IDEA          :https://www.maxer.hu/siteprotection.html
# AUTHOR        :Viktor Szépe <viktor@szepe.net>
# LICENSE       :The MIT License (MIT)
# URL           :https://github.com/szepeviktor/debian-server-tools
# BASH-VERSION  :4.2+
# LOCATION      :/usr/local/sbin/siteprotection.sh
# CRON.D        :00 *  * * *  root	/usr/local/sbin/siteprotection.sh

find /home/ -type f "(" -iname "*.php" -o -iname ".htaccess" -o -iname ".env" ")" \
    "(" -cmin -61 -o -mmin -61 ")" -printf '%p @%TH:%TM:%TS\n' \
    | grep -v -E -x '/home/[[:alnum:]]+/public_html/wp-content/cache/\S+\.php @[0-9:.]+' \

exit 0
