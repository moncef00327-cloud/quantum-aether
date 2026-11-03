<?php
/**
 * Site Health test. Reads the stored result only; it never contacts the scanner itself.
 *
 * @package QuantumReady
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

class QR_Site_Health {

	public static function init() {
		add_filter( 'site_status_tests', array( __CLASS__, 'register' ) );
	}

	/**
	 * @param array $tests Site Health tests.
	 * @return array
	 */
	public static function register( $tests ) {
		$tests['direct']['quantum_ready_tls'] = array(
			'label' => __( 'Post-quantum key exchange (HTTPS)', 'quantum-ready' ),
			'test'  => array( __CLASS__, 'run' ),
		);
		return $tests;
	}

	/**
	 * @return array Site Health result.
	 */
	public static function run() {
		$page    = admin_url( 'tools.php?page=quantum-ready' );
		$consent = get_option( 'quantum_ready_consent', 'pending' );
		$result  = QR_Checker::result();
		$base    = array(
			'badge' => array(
				'label' => __( 'Security', 'quantum-ready' ),
				'color' => 'blue',
			),
			'test'  => 'quantum_ready_tls',
		);

		if ( 'granted' !== $consent ) {
			return $base + array(
				'label'       => __( 'Post-quantum key exchange has not been checked', 'quantum-ready' ),
				'status'      => 'recommended',
				'description' => '<p>' . esc_html__( 'WordPress cannot see your web server\'s TLS settings from the inside. An external check of your domain tells you whether visitors\' connections already use post-quantum key exchange. Nothing is sent until you agree.', 'quantum-ready' ) . '</p>',
				'actions'     => sprintf( '<a href="%s">%s</a>', esc_url( $page ), esc_html__( 'Review and run the check', 'quantum-ready' ) ),
			);
		}

		if ( empty( $result['status'] ) ) {
			return $base + array(
				'label'       => __( 'Post-quantum key exchange: no result yet', 'quantum-ready' ),
				'status'      => 'recommended',
				'description' => '<p>' . esc_html__( 'The external check has not returned a result yet. You can run it from the plugin page.', 'quantum-ready' ) . '</p>',
				'actions'     => sprintf( '<a href="%s">%s</a>', esc_url( $page ), esc_html__( 'Open Quantum Ready', 'quantum-ready' ) ),
			);
		}

		$when = wp_date( get_option( 'date_format' ), (int) $result['checked_ts'] );

		if ( 'not_public' === $result['status'] ) {
			return $base + array(
				'label'       => __( 'Post-quantum key exchange: not checkable for this address', 'quantum-ready' ),
				'status'      => 'good',
				'description' => '<p>' . esc_html__( 'This site address is not reachable from the public internet (for example a local or staging site), so its TLS cannot be checked externally.', 'quantum-ready' ) . '</p>',
			);
		}

		if ( 'hybrid' === $result['status'] ) {
			$base['badge']['color'] = 'green';
			return $base + array(
				/* translators: %s: key-exchange group, e.g. X25519MLKEM768 */
				'label'       => sprintf( __( 'HTTPS uses post-quantum key exchange (%s)', 'quantum-ready' ), $result['group'] ),
				'status'      => 'good',
				/* translators: %s: date of the last check */
				'description' => '<p>' . esc_html( sprintf( __( 'Connections to this site use hybrid post-quantum key exchange, so traffic recorded today cannot later be decrypted by a quantum computer. Last checked: %s.', 'quantum-ready' ), $when ) ) . '</p>',
			);
		}

		$base['badge']['color'] = 'orange';
		return $base + array(
			'label'       => __( 'Your host has not enabled post-quantum key exchange yet', 'quantum-ready' ),
			'status'      => 'recommended',
			'description' => '<p>' . esc_html(
				sprintf(
					/* translators: 1: key-exchange group, 2: date of the last check */
					__( 'Connections currently use classical key exchange only (%1$s; checked %2$s). This is not an emergency: it means the site is not yet prepared for future quantum computers, which could decrypt traffic recorded today. Chrome, Firefox and Edge already support the hybrid group X25519MLKEM768; enabling it is a server setting controlled by your hosting provider, not by WordPress.', 'quantum-ready' ),
					$result['group'] ? $result['group'] : '?',
					$when
				)
			) . '</p>',
			'actions'     => sprintf( '<a href="%s">%s</a>', esc_url( $page ), esc_html__( 'Get a ready-made request for your host', 'quantum-ready' ) ),
		);
	}
}
