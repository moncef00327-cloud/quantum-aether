<?php
require __DIR__ . '/wp-shim.php';
// real HTTP instead of the fake one
function qr_real_get( $url ) { $ctx = stream_context_create( array( 'http' => array( 'ignore_errors' => true, 'timeout' => 60, 'header' => "User-Agent: QuantumReady/1.0 (test)\r\n" ) ) );
  $body = file_get_contents( $url, false, $ctx ); preg_match( '#HTTP/\S+ (\d+)#', $http_response_header[0], $m ); return array( 'response' => array( 'code' => (int) $m[1] ), 'body' => $body ); }
require __DIR__ . '/../quantum-ready/quantum-ready.php';
update_option( 'quantum_ready_consent', 'granted' );
foreach ( array( 'https://cloudflare.com', 'https://github.com', 'http://localhost' ) as $home ) {
  $GLOBALS['qr_home'] = $home;
  $GLOBALS['qr_http'] = qr_real_get( 'https://ather-quatum.cloud/api/v1/scan?domain=' . parse_url( $home, PHP_URL_HOST ) . '&max_age=24' );
  $r = QR_Checker::check( false ); $sh = QR_Site_Health::run();
  printf( "%-12s status=%-10s grade=%s group=%-15s | Site Health: [%s] %s\n", parse_url( $home, PHP_URL_HOST ), $r['status'], $r['grade'] ?? '-', $r['group'] ?? '-', $sh['status'], $sh['label'] );
}
