<?php

// wp eval-file elementor-check.php
// wp plugin list --fields=name,version | grep -i 'elementor'

use Elementor\Plugin;
use Elementor\Core\Utils\Version;
use Elementor\Modules\CompatibilityTag\Compatibility_Tag;
use Elementor\Modules\CompatibilityTag\Module;

wp_clean_plugins_cache(false);

$elementorPluginInstance = Plugin::$instance;

$compatibilityTagModule = $elementorPluginInstance->modules_manager->get_modules('compatibility-tag');
$reflectionModule = new ReflectionObject($compatibilityTagModule);
$getPluginsToCheckMethod = $reflectionModule->getMethod('get_plugins_to_check');
$getPluginsToCheckMethod->setAccessible(true);

$pluginsToCheck = $getPluginsToCheckMethod->invoke($compatibilityTagModule);
$activePlugins = $elementorPluginInstance->wp->get_active_plugins();

$compatibilityChecker = new Compatibility_Tag(Module::PLUGIN_VERSION_TESTED_HEADER);

foreach (
    $compatibilityChecker->check(
        Version::create_from_string(ELEMENTOR_VERSION),
        $pluginsToCheck->only($activePlugins->keys()->all())->keys()->all()
    ) as $pluginFile => $status
) {
    if ($status === Compatibility_Tag::COMPATIBLE) continue;
    WP_CLI::error(sprintf('%s: %s', $pluginFile, $status));
}

$upgrade = Plugin::$instance->upgrade;

if ($upgrade->get_task_runner()->is_running() && $upgrade->get_task_runner()->is_process_locked()) {
    WP_CLI::error('elementor:updater-running');
}

// wp eval '$u=\Elementor\Plugin::$instance->upgrade; $u->get_task_runner()->continue_run();'
if ($upgrade->get_task_runner()->is_running()) {
    WP_CLI::error('elementor:updater-queued-no-lock');
}

if (version_compare($upgrade->get_new_version(), (string) $upgrade->get_current_version(), '>')) {
    WP_CLI::error(sprintf(
        'elementor:upgrade-needed current=%s stored=%s',
        $upgrade->get_new_version(),
        $upgrade->get_current_version() ?: 'none'
    ));
}

// wp option delete elementor_elementor_updater_completed
if (get_option('elementor_elementor_updater_completed', false)) {
    WP_CLI::error('elementor:completed-notice-flag');
}
