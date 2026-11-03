<?php
require __DIR__ . '/wp-shim.php';
require __DIR__ . '/../quantum-ready/quantum-ready.php';

$fails = 0; $n = 0;
function ok( $cond, $msg ) { global $fails, $n; $n++; if ( ! $cond ) { $fails++; echo "FAIL: $msg\n"; } }
function http( $code, $body ) { return array( 'response' => array( 'code' => $code ), 'body' => json_encode( $body ) ); }
$PQ = array( 'grade' => 'A', 'post_quantum_key_exchange' => true, 'key_exchange_group' => 'X25519MLKEM768', 'tls_version' => 'TLSv1.3', 'scan_url' => 'https://ather-quatum.cloud/scan/a' );
$CL = array( 'grade' => 'B', 'post_quantum_key_exchange' => false, 'key_exchange_group' => 'x25519', 'tls_version' => 'TLSv1.3', 'scan_url' => 'https://ather-quatum.cloud/scan/b' );

// 1. activation: consent pending, nothing sent
( $GLOBALS['qr_activate'] )();
ok( get_option( 'quantum_ready_consent' ) === 'pending', 'activation sets pending' );
$GLOBALS['qr_http'] = http( 200, $PQ );
QR_Checker::check( true );
ok( count( $GLOBALS['qr_urls'] ) === 0, 'no request before consent' );
$sh = QR_Site_Health::run();
ok( $sh['status'] === 'recommended' && strpos( $sh['label'], 'not been checked' ) !== false, 'site health asks for consent' );

// 2. consent → hybrid
update_option( 'quantum_ready_consent', 'granted' );
$r = QR_Checker::check( true );
ok( $r['status'] === 'hybrid' && $r['group'] === 'X25519MLKEM768', 'hybrid result stored' );
ok( strpos( $GLOBALS['qr_urls'][0], 'https://ather-quatum.cloud/api/v1/scan?domain=shop.example.org&max_age=1' ) === 0, 'manual check URL: ' . $GLOBALS['qr_urls'][0] );
$sh = QR_Site_Health::run();
ok( $sh['status'] === 'good' && $sh['badge']['color'] === 'green', 'site health good for hybrid' );

// 3. weekly cron → classical, uses cache window 24h
$GLOBALS['qr_http'] = http( 200, $CL );
foreach ( $GLOBALS['qr_hooks']['quantum_ready_weekly_check'] as $cb ) { $cb(); }
ok( strpos( end( $GLOBALS['qr_urls'] ), 'max_age=24' ) !== false, 'weekly check uses max_age=24' );
$sh = QR_Site_Health::run();
ok( $sh['status'] === 'recommended' && $sh['badge']['color'] === 'orange', 'site health recommended for classical' );
ok( strpos( $sh['description'], 'not an emergency' ) !== false, 'no fear wording' );

// 4. rate limit / outage keep previous result
$GLOBALS['qr_http'] = http( 429, array( 'error' => 'rate_limited' ) );
$r = QR_Checker::check( false );
ok( $r['status'] === 'classical' && $r['error'] === 'rate_limited', '429 keeps previous result' );
$GLOBALS['qr_http'] = new WP_Error( 'http_request_failed' );
$r = QR_Checker::check( false );
ok( $r['status'] === 'classical' && $r['error'] === 'unavailable', 'network error keeps previous result' );

// 5. local / staging site
$GLOBALS['qr_http'] = http( 400, array( 'error' => 'private_address', 'message' => 'not public' ) );
$r = QR_Checker::check( true );
ok( $r['status'] === 'not_public', '400 → not_public' );
ok( QR_Site_Health::run()['status'] === 'good', 'not_public is not flagged' );

// 6. host messages
$res = array( 'host' => 'shop.example.org', 'group' => 'x25519' );
foreach ( array( 'en', 'de', 'ar' ) as $l ) {
	$m = QR_Host_Message::get( $l, $res );
	ok( strpos( $m, 'shop.example.org' ) !== false && strpos( $m, 'X25519MLKEM768' ) !== false && strpos( $m, 'ssl_ecdh_curve' ) !== false && strpos( $m, '/adoption' ) !== false, "host message $l complete" );
}

// 7. admin page renders without notices, shows host messages for classical
$GLOBALS['qr_http'] = http( 200, $CL );
QR_Checker::check( true );
ob_start(); QR_Admin::render(); $html = ob_get_clean();
ok( strpos( $html, 'Ask your hosting provider' ) !== false && substr_count( $html, 'qr-copy' ) === 3, 'admin shows 3 copyable messages' );
ok( strpos( $html, 'Withdraw consent' ) !== false, 'admin shows withdraw' );
update_option( 'quantum_ready_consent', 'pending' );
ob_start(); QR_Admin::render(); $html = ob_get_clean();
ok( strpos( $html, 'I agree' ) !== false && strpos( $html, 'datenschutz' ) !== false, 'consent screen with privacy link' );

// 8. deactivation clears cron
$GLOBALS['qr_cron']['quantum_ready_weekly_check'] = array( 1, 'weekly' );
( $GLOBALS['qr_deactivate'] )();
ok( ! wp_next_scheduled( 'quantum_ready_weekly_check' ), 'deactivation clears cron' );

echo "$n checks, $fails failed\n";
exit( $fails ? 1 : 0 );
