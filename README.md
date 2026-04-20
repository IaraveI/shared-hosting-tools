# Shared hosting tools

Monitor a website on shared hosting from your server through SSH.

## Installation

- Set up public key SSH authentication
- Copy binaries to `~/bin/`
- Copy these to `~/bin/`: ingest.php siteprotection.sh elementor-check.php list-woo-log-files.php
- Copy wp-cli.yml to home
- Add settings in .htaccess
- Add settings in wp-config.php
- Add cron jobs in crontab
- Copy MU plugins from mu-plugins

Edit all files as necessary.

## Usage

Run a cron job locally to tail all remote logs.

```shell
hostedsite()
{
    /usr/bin/ssh hostedsite@hoster.example.com "$@"
}

{
    hostedsite bin/logtail2 "logs/syslog-$(date --utc -d yesterday +%F).log"
    if hostedsite test -f "logs/syslog-$(date --utc +%F).log"; then
        hostedsite bin/logtail2 "logs/syslog-$(date --utc +%F).log"
    fi
} \
    | cat --show-tabs --show-nonprinting \
    | fold --width=240 \
    | sed -e '1s#^#--- System log ---\n#'
```

## Monitoring

- Apache access log
- Apache error log
- PHP error log
- WP Cron (Linux cron) output
- WooCommerce logs
- Action Scheduler failures
- [Critical site health](https://github.com/szepeviktor/critical-site-health)
- File changes (siteprotection.sh)
- [HTML page changes](https://github.com/szepeviktor/safe-website-upgrade)
- [Synthetic transaction testing](https://www.npmjs.com/package/@playwright/test)

## Tool releases

- https://packages.debian.org/sid/all/logtail/download
- https://github.com/sharkdp/bat/releases
- https://github.com/mdom/dategrep/releases
- https://wp-cli.org/#installing
- https://github.com/tstack/lnav/releases
- https://github.com/bensadeh/tailspin/releases
- https://github.com/jqlang/jq/releases
- https://getcomposer.org/download/#manual-download
- https://www.7-zip.org/
