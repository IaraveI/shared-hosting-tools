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
