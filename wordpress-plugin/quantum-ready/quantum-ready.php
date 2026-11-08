<?php
/**
 * Plugin Name:       Quantum Ready – Post-Quantum TLS Check
 * Plugin URI:        https://ather-quantum.com/adoption
 * Description:       Shows in Site Health whether your site's HTTPS already uses post-quantum key exchange (X25519MLKEM768), and gives you a ready-made request for your hosting provider. The external check runs only after you consent.
 * Version:           1.0.0
 * Requires at least: 6.0
 * Requires PHP:      7.4
 * Author:            Quantum Aether
 * Author URI:        https://ather-quantum.com
 * License:           GPL-2.0-or-later
 * License URI:       https://www.gnu.org/licenses/gpl-2.0.html
 * Text Domain:       quantum-ready
 * Domain Path:       /languages
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

define( 'QUANTUM_READY_VERSION', '1.0.0' );
define( 'QUANTUM_READY_FILE', __FILE__ );
define( 'QUANTUM_READY_DIR', plugin_dir_path( __FILE__ ) );
define( 'QUANTUM_READY_URL', plugin_dir_url( __FILE__ ) );

require_once QUANTUM_READY_DIR . 'includes/class-qr-checker.php';
require_once QUANTUM_READY_DIR . 'includes/class-qr-host-message.php';
require_once QUANTUM_READY_DIR . 'includes/class-qr-site-health.php';
require_once QUANTUM_READY_DIR . 'includes/class-qr-admin.php';

/** Weekly re-check, scheduled only while consent is granted. */
const QUANTUM_READY_CRON = 'quantum_ready_weekly_check';

register_activation_hook(
	__FILE__,
	function () {
		add_option( 'quantum_ready_consent', 'pending', '', false );
	}
);

register_deactivation_hook(
	__FILE__,
	function () {
		wp_clear_scheduled_hook( QUANTUM_READY_CRON );
	}
);

add_action(
	QUANTUM_READY_CRON,
	function () {
		if ( 'granted' === get_option( 'quantum_ready_consent' ) ) {
			QR_Checker::check( false );
		}
	}
);

QR_Site_Health::init();
QR_Admin::init();
