=== Quantum Ready – Post-Quantum TLS Check ===
Contributors: quantumaether
Tags: security, ssl, tls, https, site health
Requires at least: 6.0
Tested up to: 7.1
Requires PHP: 7.4
Stable tag: 1.0.0
License: GPLv2 or later
License URI: https://www.gnu.org/licenses/gpl-2.0.html

See in Site Health whether your HTTPS already uses post-quantum key exchange, and ask your host to enable it in one click.

== Description ==

Chrome, Firefox and Edge already protect connections with **hybrid post-quantum key exchange (X25519MLKEM768, ML-KEM / FIPS 203)** — but only when the web server offers it. Traffic that uses classical key exchange can be recorded today and decrypted later by a large quantum computer ("harvest now, decrypt later").

WordPress cannot see your web server's TLS settings from the inside, and on most hosting plans you cannot change them yourself. Quantum Ready closes that gap:

* **Site Health test** – a new item under Tools → Site Health shows whether visitors' connections to your site use post-quantum key exchange.
* **Ready-made request for your host** – if they don't, you get a polite message in English, German or Arabic that includes the exact technical change for your host's team. You copy it and send it yourself.
* **Weekly re-check** – the result stays current without you doing anything.
* **Consent first** – nothing is sent anywhere until you agree on the plugin page. You can withdraw consent at any time; the stored result is then deleted.
* **No dashboard banners, no upsell nags.**

The check is the same one a browser performs: it connects to your domain on port 443 and records which key exchange the server picks. It never logs in, never sends data to your site, and never tests for vulnerabilities.

== External services ==

This plugin connects to the **Quantum Aether scanner** (https://ather-quatum.cloud), operated by Omer Alsaloum, Braunau am Inn, Austria, to check which TLS key exchange your site's public address negotiates. WordPress cannot determine this from inside the server.

* **What is sent:** your site's hostname (for example `example.com`) as part of a request to `https://ather-quatum.cloud/api/v1/scan`. Like every HTTP request, it also reveals your server's IP address and the plugin's user-agent string. No visitor data, no content and no personal data are sent.
* **When:** only after an administrator gives consent on Tools → Quantum Ready; then once immediately, once a week, and when the administrator presses "Check again" (at most once per hour).
* **Why:** to report the result in Site Health and on the plugin page.
* **Terms of use:** https://ather-quatum.cloud/agb?lang=en
* **Privacy policy:** https://ather-quatum.cloud/datenschutz?lang=en

The scanner stores the hostname and the scan result. Results of public domains may appear in aggregate, anonymous statistics such as https://ather-quatum.cloud/adoption.

== Installation ==

1. Install and activate the plugin.
2. Go to **Tools → Quantum Ready** and press **"I agree – check my site now"**.
3. Open **Tools → Site Health** to see the result alongside WordPress's other checks.

== Frequently Asked Questions ==

= My site shows "classical key exchange only". Is it hacked or insecure? =

No. Your HTTPS connection is still encrypted and safe against today's computers. "Classical only" means the site is not yet prepared for future quantum computers. It is a readiness item, not an emergency.

= Can I fix it myself? =

Usually not on shared or managed hosting: the TLS configuration belongs to your hosting provider. Use the ready-made message on the plugin page. If you run your own server, the message contains the exact setting (OpenSSL 3.5 or newer plus one configuration line).

= My site is behind Cloudflare. =

Then the check sees Cloudflare's edge, which already offers X25519MLKEM768. The connection between Cloudflare and your server is a separate setting in Cloudflare.

= Does the plugin slow down my site? =

No. It does nothing on the front end. The check runs in the background once a week via WP-Cron, and Site Health only reads the stored result.

= What about local or staging sites? =

They are not reachable from the internet, so the plugin reports that they cannot be checked externally.

= How do I stop the external checks? =

Press "Withdraw consent" on Tools → Quantum Ready, or deactivate the plugin. Uninstalling removes everything the plugin stored.

== Screenshots ==

1. Site Health test when the host has not enabled post-quantum key exchange yet.
2. The plugin page with the result and the ready-made request for your host.

== Changelog ==

= 1.0.0 =
* First release: Site Health test, consent screen, weekly check, ready-made host request in English, German and Arabic.
