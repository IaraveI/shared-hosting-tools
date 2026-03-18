<?php

// Write an Apache-like access.log
register_shutdown_function(function () {
    file_put_contents(
        dirname(__DIR__).'/access.log',
        sprintf(
            '%s - - [%s] "%s %s %s" %d %.2f "%s" "%s"' . PHP_EOL,
            $_SERVER['REMOTE_ADDR'] ?? '127.0.0.1',
            date('d/M/Y:H:i:s O'),
            $_SERVER['REQUEST_METHOD'] ?? 'GET',
            $_SERVER['REQUEST_URI'] ?? '/',
            $_SERVER['SERVER_PROTOCOL'] ?? 'HTTP/1.1',
            http_response_code(),
            // sys_getloadavg()[0] ?? 0, // CPU load
            timer_float(), // Seconds since the PHP started
            $_SERVER['HTTP_REFERER'] ?? '-',
            $_SERVER['HTTP_USER_AGENT'] ?? '-'
        ),
        FILE_APPEND | LOCK_EX
    );
});

// Run WP-Cron from linux crontab
define('DISABLE_WP_CRON', true);

// Disable fatal error handler
if (php_sapi_name() === 'cli' && defined('DOING_CRON') && DOING_CRON) define('WP_DISABLE_FATAL_ERROR_HANDLER', true);

// wp-redis: Persistent object cache
$redis_server = [
    'host' => '127.0.0.1',
    'port' => 6379,
    'auth' => 'password', // ['user', 'password'],
    'database' => 0,
];
define('WP_CACHE_KEY_SALT', 'SITE-SHORT:');
define('WP_REDIS_DEFAULT_EXPIRE_SECONDS', 86400);
