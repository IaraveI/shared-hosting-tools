<?php

// Disable fatal error handler
if (php_sapi_name() === 'cli' && defined('DOING_CRON') && DOING_CRON) define('WP_DISABLE_FATAL_ERROR_HANDLER', true);
