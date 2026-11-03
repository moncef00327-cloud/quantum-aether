<?php
/**
 * Admin page (Tools → Quantum Ready): consent, result, re-check, revoke, host message.
 *
 * No dashboard banners: the plugin speaks only on its own page and in Site Health.
 *
 * @package QuantumReady
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

class QR_Admin {

	const SLUG = 'quantum-ready';

	public static function init() {
		add_action( 'admin_menu', array( __CLASS__, 'menu' ) );
		add_action( 'admin_post_quantum_ready', array( __CLASS__, 'handle' ) );
		add_action( 'admin_enqueue_scripts', array( __CLASS__, 'assets' ) );
		add_filter( 'plugin_action_links_' . plugin_basename( QUANTUM_READY_FILE ), array( __CLASS__, 'action_link' ) );
	}

	public static function menu() {
		add_management_page(
			__( 'Quantum Ready', 'quantum-ready' ),
			__( 'Quantum Ready', 'quantum-ready' ),
			'manage_options',
			self::SLUG,
			array( __CLASS__, 'render' )
		);
	}

	/**
	 * @param array $links Plugin row links.
	 * @return array
	 */
	public static function action_link( $links ) {
		array_unshift(
			$links,
			sprintf( '<a href="%s">%s</a>', esc_url( admin_url( 'tools.php?page=' . self::SLUG ) ), esc_html__( 'Check', 'quantum-ready' ) )
		);
		return $links;
	}

	/**
	 * @param string $hook Current admin page hook.
	 */
	public static function assets( $hook ) {
		if ( 'tools_page_' . self::SLUG !== $hook ) {
			return;
		}
		wp_enqueue_script( 'quantum-ready-admin', QUANTUM_READY_URL . 'assets/admin.js', array(), QUANTUM_READY_VERSION, true );
		wp_localize_script( 'quantum-ready-admin', 'QuantumReady', array( 'copied' => __( 'Copied', 'quantum-ready' ) ) );
	}

	/** Form handler (POST → redirect → GET, so reloading never repeats an action). */
	public static function handle() {
		if ( ! current_user_can( 'manage_options' ) ) {
			wp_die( esc_html__( 'You are not allowed to do this.', 'quantum-ready' ), 403 );
		}
		check_admin_referer( 'quantum_ready' );
		$do     = isset( $_POST['qr_do'] ) ? sanitize_key( wp_unslash( $_POST['qr_do'] ) ) : '';
		$notice = '';

		if ( 'grant' === $do ) {
			update_option( 'quantum_ready_consent', 'granted', false );
			if ( ! wp_next_scheduled( QUANTUM_READY_CRON ) ) {
				wp_schedule_event( time() + WEEK_IN_SECONDS, 'weekly', QUANTUM_READY_CRON );
			}
			QR_Checker::check( true );
			$notice = 'checked';
		} elseif ( 'recheck' === $do && 'granted' === get_option( 'quantum_ready_consent' ) ) {
			if ( QR_Checker::can_check_now() ) {
				QR_Checker::check( true );
				$notice = 'checked';
			} else {
				$notice = 'wait';
			}
		} elseif ( 'revoke' === $do ) {
			update_option( 'quantum_ready_consent', 'revoked', false );
			delete_option( QR_Checker::OPTION );
			wp_clear_scheduled_hook( QUANTUM_READY_CRON );
			$notice = 'revoked';
		}

		wp_safe_redirect( add_query_arg( array( 'page' => self::SLUG, 'qr_notice' => $notice ), admin_url( 'tools.php' ) ) );
		exit;
	}

	/**
	 * @param string $do Action name.
	 * @param string $label Button text.
	 * @param string $class Button class.
	 */
	private static function button( $do, $label, $class = 'button' ) {
		?>
		<form method="post" action="<?php echo esc_url( admin_url( 'admin-post.php' ) ); ?>" style="display:inline-block;margin-inline-end:8px;">
			<input type="hidden" name="action" value="quantum_ready">
			<input type="hidden" name="qr_do" value="<?php echo esc_attr( $do ); ?>">
			<?php wp_nonce_field( 'quantum_ready' ); ?>
			<button type="submit" class="<?php echo esc_attr( $class ); ?>"><?php echo esc_html( $label ); ?></button>
		</form>
		<?php
	}

	public static function render() {
		if ( ! current_user_can( 'manage_options' ) ) {
			return;
		}
		$consent = get_option( 'quantum_ready_consent', 'pending' );
		$result  = QR_Checker::result();
		$base    = QR_Checker::api_base();
		$notice  = isset( $_GET['qr_notice'] ) ? sanitize_key( wp_unslash( $_GET['qr_notice'] ) ) : ''; // phpcs:ignore WordPress.Security.NonceVerification.Recommended
		$notices = array(
			'checked' => array( 'success', __( 'Check complete.', 'quantum-ready' ) ),
			'wait'    => array( 'info', __( 'Your site was checked less than an hour ago. Please try again later.', 'quantum-ready' ) ),
			'revoked' => array( 'info', __( 'Consent withdrawn. The stored result was deleted and no further checks will run.', 'quantum-ready' ) ),
		);
		?>
		<div class="wrap">
			<h1><?php esc_html_e( 'Quantum Ready – Post-Quantum TLS Check', 'quantum-ready' ); ?></h1>
			<?php if ( isset( $notices[ $notice ] ) ) : ?>
				<div class="notice notice-<?php echo esc_attr( $notices[ $notice ][0] ); ?> is-dismissible"><p><?php echo esc_html( $notices[ $notice ][1] ); ?></p></div>
			<?php endif; ?>

			<?php if ( 'granted' !== $consent ) : ?>
				<div class="card" style="max-width:760px;">
					<h2><?php esc_html_e( 'Check your site from the outside', 'quantum-ready' ); ?></h2>
					<p><?php esc_html_e( 'Chrome, Firefox and Edge already protect connections with hybrid post-quantum key exchange (X25519MLKEM768) when the server offers it. WordPress cannot see your server\'s TLS settings from the inside, so this plugin asks an external scanner to connect to your domain, exactly as a browser does, and report which key exchange it gets.', 'quantum-ready' ); ?></p>
					<p><strong><?php esc_html_e( 'What is sent:', 'quantum-ready' ); ?></strong> <?php echo esc_html( sprintf( /* translators: %s: hostname */ __( 'only your site\'s hostname (%s), at most once a week plus when you press "Check again". No visitor data, content or personal data.', 'quantum-ready' ), QR_Checker::host() ) ); ?></p>
					<p><strong><?php esc_html_e( 'Service:', 'quantum-ready' ); ?></strong>
						<a href="<?php echo esc_url( $base ); ?>" target="_blank" rel="noopener">Quantum Aether</a> ·
						<a href="<?php echo esc_url( $base . '/datenschutz?lang=en' ); ?>" target="_blank" rel="noopener"><?php esc_html_e( 'Privacy policy', 'quantum-ready' ); ?></a> ·
						<a href="<?php echo esc_url( $base . '/agb?lang=en' ); ?>" target="_blank" rel="noopener"><?php esc_html_e( 'Terms', 'quantum-ready' ); ?></a>
					</p>
					<p><?php self::button( 'grant', __( 'I agree – check my site now', 'quantum-ready' ), 'button button-primary' ); ?></p>
					<p class="description"><?php esc_html_e( 'You can withdraw consent at any time on this page; the stored result is then deleted.', 'quantum-ready' ); ?></p>
				</div>
			<?php else : ?>
				<?php self::render_result( $result, $base ); ?>
			<?php endif; ?>
		</div>
		<?php
	}

	/**
	 * @param array  $result Stored result.
	 * @param string $base   Scanner base URL.
	 */
	private static function render_result( $result, $base ) {
		$status = isset( $result['status'] ) ? $result['status'] : '';
		$errors = array(
			'rate_limited' => __( 'The scanner is busy right now; the next weekly check will retry automatically.', 'quantum-ready' ),
			'unavailable'  => __( 'The scanner could not be reached; the next weekly check will retry automatically.', 'quantum-ready' ),
		);
		?>
		<div class="card" style="max-width:760px;">
			<h2><?php esc_html_e( 'Result', 'quantum-ready' ); ?></h2>
			<?php if ( ! empty( $result['error'] ) && isset( $errors[ $result['error'] ] ) ) : ?>
				<p class="description"><?php echo esc_html( $errors[ $result['error'] ] ); ?></p>
			<?php endif; ?>

			<?php if ( 'hybrid' === $status ) : ?>
				<p><span style="display:inline-block;padding:3px 12px;border-radius:12px;background:#00a32a;color:#fff;"><?php esc_html_e( 'Post-quantum ready', 'quantum-ready' ); ?></span></p>
				<p><?php echo esc_html( sprintf( /* translators: 1: group, 2: grade */ __( 'Visitors\' connections use %1$s (grade %2$s). Nothing to do.', 'quantum-ready' ), $result['group'], $result['grade'] ) ); ?></p>
			<?php elseif ( 'classical' === $status ) : ?>
				<p><span style="display:inline-block;padding:3px 12px;border-radius:12px;background:#dba617;color:#1d2327;"><?php esc_html_e( 'Classical key exchange only', 'quantum-ready' ); ?></span></p>
				<p><?php echo esc_html( sprintf( /* translators: 1: group, 2: grade */ __( 'Visitors\' connections use %1$s (grade %2$s). Not an emergency: it means traffic recorded today could be decrypted by a future quantum computer. The setting belongs to your hosting provider.', 'quantum-ready' ), $result['group'] ? $result['group'] : '?', $result['grade'] ) ); ?></p>
			<?php elseif ( 'not_public' === $status ) : ?>
				<p><?php esc_html_e( 'This site address is not reachable from the public internet (for example a local or staging site), so it cannot be checked externally.', 'quantum-ready' ); ?></p>
			<?php else : ?>
				<p><?php esc_html_e( 'No result yet.', 'quantum-ready' ); ?></p>
			<?php endif; ?>

			<?php if ( ! empty( $result['checked_ts'] ) ) : ?>
				<p class="description"><?php echo esc_html( sprintf( /* translators: %s: date and time */ __( 'Last checked: %s. Re-checked automatically every week.', 'quantum-ready' ), wp_date( get_option( 'date_format' ) . ' ' . get_option( 'time_format' ), (int) $result['checked_ts'] ) ) ); ?></p>
			<?php endif; ?>
			<p>
				<?php self::button( 'recheck', __( 'Check again', 'quantum-ready' ) ); ?>
				<?php if ( ! empty( $result['scan_url'] ) ) : ?>
					<a href="<?php echo esc_url( $result['scan_url'] ); ?>" target="_blank" rel="noopener"><?php esc_html_e( 'Full technical result', 'quantum-ready' ); ?></a>
				<?php endif; ?>
			</p>
		</div>

		<?php if ( 'classical' === $status ) : ?>
			<div class="card" style="max-width:760px;">
				<h2><?php esc_html_e( 'Ask your hosting provider', 'quantum-ready' ); ?></h2>
				<p><?php esc_html_e( 'Copy the message in the language your host uses and send it through their support chat or ticket system. It includes the exact technical change for their team.', 'quantum-ready' ); ?></p>
				<?php foreach ( QR_Host_Message::LANGUAGES as $code => $name ) : ?>
					<details style="margin:8px 0;" <?php echo 'en' === $code ? 'open' : ''; ?>>
						<summary><strong><?php echo esc_html( $name ); ?></strong></summary>
						<textarea readonly rows="11" class="large-text" id="qr-msg-<?php echo esc_attr( $code ); ?>" dir="<?php echo 'ar' === $code ? 'rtl' : 'ltr'; ?>"><?php echo esc_textarea( QR_Host_Message::get( $code, $result ) ); ?></textarea>
						<p><button type="button" class="button qr-copy" data-target="qr-msg-<?php echo esc_attr( $code ); ?>"><?php esc_html_e( 'Copy', 'quantum-ready' ); ?></button></p>
					</details>
				<?php endforeach; ?>
				<p class="description">
					<a href="<?php echo esc_url( $base . '/adoption' ); ?>" target="_blank" rel="noopener"><?php esc_html_e( 'Which large sites already use it', 'quantum-ready' ); ?></a> ·
					<a href="<?php echo esc_url( $base . '/monitoring' ); ?>" target="_blank" rel="noopener"><?php esc_html_e( 'Daily monitoring for several domains', 'quantum-ready' ); ?></a>
				</p>
			</div>
		<?php endif; ?>

		<div class="card" style="max-width:760px;">
			<h2><?php esc_html_e( 'Privacy', 'quantum-ready' ); ?></h2>
			<p><?php esc_html_e( 'Only your hostname is sent to the scanner. Withdrawing consent stops all checks and deletes the stored result.', 'quantum-ready' ); ?></p>
			<p><?php self::button( 'revoke', __( 'Withdraw consent', 'quantum-ready' ) ); ?></p>
		</div>
		<?php
	}
}
