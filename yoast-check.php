<?php

// wp eval-file yoast-check.php
// wp plugin list --fields=name,version | grep -i 'wordpress-seo'

require_once ABSPATH.'wp-admin/includes/file.php';
require_once ABSPATH.'wp-admin/includes/class-wp-upgrader.php';

global $wp_filesystem;
WP_Filesystem();

$r = (new \Yoast\WP\SEO\Integrations\Admin\Check_Required_Version())->check_required_version(
    WP_PLUGIN_DIR.'/wordpress-seo-premium/',
    null,
    new Plugin_Upgrader()
);

if (is_wp_error($r)) {
    WP_CLI::error('wordpress-seo-premium: '.$r->get_error_message());
}

$r = (new \Yoast\WP\SEO\Integrations\Admin\Check_Required_Version())->check_required_version(
    WP_PLUGIN_DIR.'/wpseo-woocommerce/',
    null,
    new Plugin_Upgrader()
);

if (is_wp_error($r)) {
    WP_CLI::error('wpseo-woocommerce: '.$r->get_error_message());
}
