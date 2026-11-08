<?php
/**
 * External check client.
 *
 * Asks the Quantum Aether scanner (https://ather-quantum.com) which TLS key-exchange group this
 * site's public hostname negotiates. Only the hostname is sent, and only after the site admin
 * granted consent (see QR_Admin). The result is stored in one option; nothing else is kept.
 *
 * @package QuantumReady
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

class QR_Checker {

	const OPTION = 'quantum_ready_result';

	/** Manual "check again" is limited to once per hour per site. */
	const MANUAL_INTERVAL = HOUR_IN_SECONDS;

	/**
	 * Scanner base URL. Filterable for self-hosted scanners.
	 *
	 * @return string
	 */
	public static function api_base() {
		return untrailingslashit( apply_filters( 'quantum_ready_api_base', 'https://ather-quantum.com' ) );
	}

	/**
	 * The hostname that visitors reach.
	 *
	 * @return string
	 */
	public static function host() {
		return strtolower( (string) wp_parse_url( home_url(), PHP_URL_HOST ) );
	}

	/**
	 * Latest stored result (empty array if none).
	 *
	 * @return array
	 */
	public static function result() {
		$result = get_option( self::OPTION, array() );
		return is_array( $result ) ? $result : array();
	}

	/**
	 * Whether a manual re-check is allowed right now.
	 *
	 * @return bool
	 */
	public static function can_check_now() {
		$result = self::result();
		return empty( $result['checked_ts'] ) || ( time() - (int) $result['checked_ts'] ) >= self::MANUAL_INTERVAL;
	}

	/**
	 * Run the check and store the outcome.
	 *
	 * @param bool $manual True when the admin clicked "check"; uses a fresher result.
	 * @return array The stored result.
	 */
	public static function check( $manual ) {
		if ( 'granted' !== get_option( 'quantum_ready_consent' ) ) {
			return self::result();
		}
		$host = self::host();
		// Weekly runs accept a result up to 24 h old from the scanner's cache; this keeps shared
		// hosting (many sites behind one IP address) clear of the scanner's per-IP rate limit.
		$max_age = $manual ? 1 : 24;
		$url     = add_query_arg(
			array(
				'domain'  => rawurlencode( $host ),
				'max_age' => $max_age,
			),
			self::api_base() . '/api/v1/scan'
		);

		$response = wp_remote_get(
			$url,
			array(
				'timeout'     => 45,
				'redirection' => 2,
				'user-agent'  => 'QuantumReady/' . QUANTUM_READY_VERSION . ' (WordPress plugin)',
			)
		);

		return self::store( self::interpret( $host, $response ) );
	}

	/**
	 * Turn an HTTP response into a result array. Pure function, unit-tested.
	 *
	 * @param string         $host     Hostname that was checked.
	 * @param array|WP_Error $response wp_remote_get() return value.
	 * @return array
	 */
	public static function interpret( $host, $response ) {
		$previous = self::result();
		$now      = time();

		if ( is_wp_error( $response ) ) {
			return array_merge( $previous, array( 'error' => 'unavailable', 'error_ts' => $now ) );
		}
		$code = (int) wp_remote_retrieve_response_code( $response );
		$body = json_decode( (string) wp_remote_retrieve_body( $response ), true );

		if ( 429 === $code ) {
			return array_merge( $previous, array( 'error' => 'rate_limited', 'error_ts' => $now ) );
		}
		if ( 400 === $code ) {
			// Not a public domain (localhost, intranet, staging behind a firewall …).
			return array(
				'host'       => $host,
				'status'     => 'not_public',
				'message'    => is_array( $body ) && isset( $body['message'] ) ? sanitize_text_field( $body['message'] ) : '',
				'checked_ts' => $now,
			);
		}
		if ( 200 !== $code || ! is_array( $body ) || ! isset( $body['grade'] ) ) {
			return array_merge( $previous, array( 'error' => 'unavailable', 'error_ts' => $now ) );
		}

		return array(
			'host'       => $host,
			'status'     => ! empty( $body['post_quantum_key_exchange'] ) ? 'hybrid' : 'classical',
			'grade'      => sanitize_text_field( (string) $body['grade'] ),
			'group'      => isset( $body['key_exchange_group'] ) ? sanitize_text_field( (string) $body['key_exchange_group'] ) : '',
			'tls'        => isset( $body['tls_version'] ) ? sanitize_text_field( (string) $body['tls_version'] ) : '',
			'scan_url'   => isset( $body['scan_url'] ) ? esc_url_raw( (string) $body['scan_url'] ) : '',
			'checked_ts' => $now,
		);
	}

	/**
	 * @param array $result Result to persist.
	 * @return array
	 */
	private static function store( $result ) {
		update_option( self::OPTION, $result, false );
		return $result;
	}
}
