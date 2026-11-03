<?php
/**
 * Ready-made request to the hosting provider (EN / DE / AR).
 *
 * The site owner copies and sends it themselves; the plugin never contacts the host.
 *
 * @package QuantumReady
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

class QR_Host_Message {

	const LANGUAGES = array(
		'en' => 'English',
		'de' => 'Deutsch',
		'ar' => 'العربية',
	);

	/**
	 * @param string $lang  en|de|ar.
	 * @param array  $result Latest check result.
	 * @return string
	 */
	public static function get( $lang, $result ) {
		$host     = ! empty( $result['host'] ) ? $result['host'] : QR_Checker::host();
		$group    = ! empty( $result['group'] ) ? $result['group'] : 'X25519';
		$base     = QR_Checker::api_base();
		$guide    = $base . '/guides/post-quantum-tls-apache-caddy-haproxy-cloudflare';
		$adoption = $base . '/adoption';

		switch ( $lang ) {
			case 'de':
				return sprintf(
					"Guten Tag,\n\nich betreibe die Website %1\$s bei Ihnen. Eine externe TLS-Prüfung zeigt, dass der Server derzeit nur den klassischen Schlüsselaustausch (%2\$s) aushandelt, aber noch nicht den hybriden Post-Quanten-Schlüsselaustausch X25519MLKEM768, den Chrome, Firefox und Edge bereits standardmäßig anbieten.\n\nKönnten Sie X25519MLKEM768 für meine Website aktivieren (mit X25519 als Rückfalloption, damit ältere Browser weiter funktionieren)?\n\nFür Ihr technisches Team: Nötig ist OpenSSL 3.5 oder neuer; dann genügt eine Zeile in der TLS-Konfiguration (z. B. nginx: ssl_ecdh_curve X25519MLKEM768:X25519:prime256v1;). Anleitung für nginx, Apache, Caddy, HAProxy und Cloudflare: %3\$s\n\nWelche großen Websites bereits umgestellt haben: %4\$s\n\nVielen Dank!",
					$host,
					$group,
					$guide,
					$adoption
				);
			case 'ar':
				return sprintf(
					"مرحبًا،\n\nأستضيف لديكم الموقع %1\$s. أظهر فحص TLS خارجي أن الخادم يتفق حاليًا على تبادل المفاتيح التقليدي فقط (%2\$s)، ولم يفعّل بعد تبادل المفاتيح الهجين المقاوم للحوسبة الكمومية X25519MLKEM768 الذي تعرضه Chrome وFirefox وEdge افتراضيًا.\n\nهل يمكنكم تفعيل X25519MLKEM768 لموقعي، مع إبقاء X25519 احتياطيًا حتى تعمل المتصفحات القديمة كما هي؟\n\nلفريقكم التقني: يلزم OpenSSL 3.5 أو أحدث، ثم سطر واحد في إعداد TLS (في nginx مثلًا: ssl_ecdh_curve X25519MLKEM768:X25519:prime256v1;). الدليل لـ nginx وApache وCaddy وHAProxy وCloudflare: %3\$s\n\nالمواقع الكبرى التي فعّلته: %4\$s\n\nشكرًا لكم.",
					$host,
					$group,
					$guide,
					$adoption
				);
			case 'en':
			default:
				return sprintf(
					"Hello,\n\nI host the website %1\$s with you. An external TLS check shows the server currently negotiates classical key exchange only (%2\$s) and does not yet offer the hybrid post-quantum key exchange X25519MLKEM768, which Chrome, Firefox and Edge already offer by default.\n\nCould you enable X25519MLKEM768 for my site, keeping X25519 as a fallback so older browsers keep working?\n\nFor your technical team: it needs OpenSSL 3.5 or newer, then one line in the TLS configuration (e.g. nginx: ssl_ecdh_curve X25519MLKEM768:X25519:prime256v1;). Guide for nginx, Apache, Caddy, HAProxy and Cloudflare: %3\$s\n\nWhich large sites have already switched: %4\$s\n\nThank you!",
					$host,
					$group,
					$guide,
					$adoption
				);
		}
	}
}
