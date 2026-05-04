#!/usr/bin/env php
<?php
// Minimal WooCommerce log ingester.

ini_set('error_log', getenv('HOME') . '/logs/ingest-php-error.log');
date_default_timezone_set('UTC');

require dirname(__DIR__) . '/public_html/wp-load.php';

$user = getenv('USER') ?: getenv('LOGNAME') ?: get_current_user();
$tag = $argv[1] ?? 'stdout';

$logger = wc_get_logger();

while (($line = fgets(STDIN)) !== false) {
    $logger->info(rtrim($line, "\r\n"), ['source' => $tag, 'user' => $user]);
}
