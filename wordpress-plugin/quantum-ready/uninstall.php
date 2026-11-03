<?php
/**
 * Removes everything the plugin stored.
 *
 * @package QuantumReady
 */

if ( ! defined( 'WP_UNINSTALL_PLUGIN' ) ) {
	exit;
}

delete_option( 'quantum_ready_consent' );
delete_option( 'quantum_ready_result' );
wp_clear_scheduled_hook( 'quantum_ready_weekly_check' );
