<?php
// Minimal WordPress function shims so the plugin's logic can be tested without a WordPress install.
error_reporting( E_ALL );
set_error_handler( function ( $no, $str, $file, $line ) { throw new ErrorException( $str, 0, $no, $file, $line ); } );
define( 'ABSPATH', '/tmp/' );
define( 'HOUR_IN_SECONDS', 3600 );
define( 'WEEK_IN_SECONDS', 604800 );
$GLOBALS['qr_options'] = array();
$GLOBALS['qr_http']    = null;   // next fake response
$GLOBALS['qr_urls']    = array();
$GLOBALS['qr_hooks']   = array();
$GLOBALS['qr_cron']    = array();
class WP_Error { public $code; function __construct( $c = '', $m = '' ) { $this->code = $c; } }
function is_wp_error( $x ) { return $x instanceof WP_Error; }
function get_option( $k, $d = false ) { return array_key_exists( $k, $GLOBALS['qr_options'] ) ? $GLOBALS['qr_options'][ $k ] : $d; }
function update_option( $k, $v, $a = null ) { $GLOBALS['qr_options'][ $k ] = $v; return true; }
function add_option( $k, $v, $d = '', $a = null ) { if ( ! array_key_exists( $k, $GLOBALS['qr_options'] ) ) { $GLOBALS['qr_options'][ $k ] = $v; } return true; }
function delete_option( $k ) { unset( $GLOBALS['qr_options'][ $k ] ); return true; }
function home_url() { return $GLOBALS['qr_home'] ?? 'https://shop.example.org'; }
function admin_url( $p = '' ) { return 'https://shop.example.org/wp-admin/' . $p; }
function wp_parse_url( $u, $c = -1 ) { return parse_url( $u, $c ); }
function apply_filters( $t, $v ) { return $v; }
function untrailingslashit( $s ) { return rtrim( $s, '/\\' ); }
function add_query_arg( $args, $url ) { return $url . ( strpos( $url, '?' ) === false ? '?' : '&' ) . http_build_query( $args ); }
function wp_remote_get( $url, $args = array() ) { $GLOBALS['qr_urls'][] = $url; return $GLOBALS['qr_http']; }
function wp_remote_retrieve_response_code( $r ) { return $r['response']['code']; }
function wp_remote_retrieve_body( $r ) { return $r['body']; }
function sanitize_text_field( $s ) { return trim( strip_tags( (string) $s ) ); }
function sanitize_key( $s ) { return preg_replace( '/[^a-z0-9_\-]/', '', strtolower( $s ) ); }
function esc_url_raw( $s ) { return $s; }
function esc_url( $s ) { return htmlspecialchars( $s, ENT_QUOTES ); }
function esc_html( $s ) { return htmlspecialchars( (string) $s, ENT_QUOTES ); }
function esc_attr( $s ) { return htmlspecialchars( (string) $s, ENT_QUOTES ); }
function esc_textarea( $s ) { return htmlspecialchars( (string) $s, ENT_QUOTES ); }
function __( $s, $d = null ) { return $s; }
function esc_html__( $s, $d = null ) { return esc_html( $s ); }
function esc_html_e( $s, $d = null ) { echo esc_html( $s ); }
function wp_date( $f, $ts ) { return gmdate( 'Y-m-d H:i', $ts ); }
function add_filter( $h, $cb ) { $GLOBALS['qr_hooks'][ $h ][] = $cb; }
function add_action( $h, $cb, $p = 10, $a = 1 ) { $GLOBALS['qr_hooks'][ $h ][] = $cb; }
function plugin_dir_path( $f ) { return dirname( $f ) . '/'; }
function plugin_dir_url( $f ) { return 'https://shop.example.org/wp-content/plugins/quantum-ready/'; }
function plugin_basename( $f ) { return 'quantum-ready/quantum-ready.php'; }
function register_activation_hook( $f, $cb ) { $GLOBALS['qr_activate'] = $cb; }
function register_deactivation_hook( $f, $cb ) { $GLOBALS['qr_deactivate'] = $cb; }
function wp_clear_scheduled_hook( $h ) { unset( $GLOBALS['qr_cron'][ $h ] ); }
function wp_next_scheduled( $h ) { return $GLOBALS['qr_cron'][ $h ] ?? false; }
function wp_schedule_event( $t, $r, $h ) { $GLOBALS['qr_cron'][ $h ] = array( $t, $r ); }
function current_user_can( $c ) { return true; }
function wp_nonce_field( $a ) { echo '<input type="hidden" name="_wpnonce" value="x">'; }
function wp_unslash( $v ) { return $v; }
