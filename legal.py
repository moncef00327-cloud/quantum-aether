# legal.py
# الصفحات القانونية للنمسا (Impressum، Datenschutz، AGB) بالألمانية والإنجليزية.
# كل بيان شخصي أو تجاري غير معروف بعد مكتوب كخانة [بين قوسين] ليملأها صاحب الموقع.
# المحتوى HTML مكتوب هنا يدوياً، لا يأتي من المستخدم.

P = '<mark class="placeholder">[{}]</mark>'
OWNER = "Omer Alsaloum"
ADDRESS = "Sparkaßen 11/12, 5280 Braunau am Inn, Österreich"
ADDRESS_EN = "Sparkaßen 11/12, 5280 Braunau am Inn, Austria"
EMAIL = '<a href="mailto:sajad.vip56@gmail.com">sajad.vip56@gmail.com</a>'

PAGES = {
    "impressum": {
        "de": {
            "title": "Impressum",
            "body": f"""
<p>Angaben gemäß § 5 E-Commerce-Gesetz (ECG) und Offenlegung gemäß § 25 Mediengesetz (MedienG).</p>
<h2>Medieninhaber und Diensteanbieter</h2>
<p>{OWNER}<br>{ADDRESS}</p>
<p>E-Mail: {EMAIL}</p>
<h2>Unternehmensangaben</h2>
<ul>
<li>Unternehmensgegenstand: IT-Dienstleistungen; Betrieb eines Online-Dienstes zur Prüfung der Post-Quanten-Bereitschaft von TLS-Verbindungen</li>
<li>Umsatzsteuer: Kleinunternehmer gemäß § 6 Abs. 1 Z 27 UStG; keine UID-Nummer</li>
<li>Nicht im Firmenbuch eingetragen</li>
</ul>
<h2>Blattlinie (§ 25 Abs. 4 MedienG)</h2>
<p>Information über Post-Quanten-Kryptographie und TLS-Sicherheit sowie Angebot eines Prüf- und Überwachungsdienstes.</p>
""",
        },
        "en": {
            "title": "Imprint (Impressum)",
            "body": f"""
<p>Information pursuant to § 5 Austrian E-Commerce Act (ECG) and disclosure pursuant to § 25 Media Act (MedienG).</p>
<h2>Media owner and service provider</h2>
<p>{OWNER}<br>{ADDRESS_EN}</p>
<p>Email: {EMAIL}</p>
<h2>Business details</h2>
<ul>
<li>Business purpose: IT services; operation of an online service that checks the post-quantum readiness of TLS connections</li>
<li>VAT: small business under § 6(1)(27) UStG; no VAT ID</li>
<li>Not registered in the company register (Firmenbuch)</li>
</ul>
<h2>Editorial policy (§ 25(4) MedienG)</h2>
<p>Information about post-quantum cryptography and TLS security, and a scanning and monitoring service.</p>
<p class="muted small">In case of doubt the German version applies.</p>
""",
        },
    },
    "datenschutz": {
        "de": {
            "title": "Datenschutzerklärung",
            "body": f"""
<h2>1. Verantwortlicher</h2>
<p>{OWNER}, {ADDRESS}, E-Mail: {EMAIL}</p>

<h2>2. Hosting</h2>
<p>Die Website läuft auf einem Server der The Constant Company, LLC („Vultr“, USA) im Rechenzentrum London, Vereinigtes Königreich. Für das Vereinigte Königreich besteht ein Angemessenheitsbeschluss der EU-Kommission. Auftragsverarbeitungsvertrag nach Art. 28 DSGVO: {P.format("bitte bestätigen, dass der Vultr-AVV/DPA akzeptiert wurde")}.</p>

<h2>3. Server-Protokolle</h2>
<p>Bei jedem Aufruf speichert der Server IP-Adresse, Datum und Uhrzeit, aufgerufene Adresse, Referrer und Browserkennung. Zweck: Betrieb und Sicherheit der Website. Rechtsgrundlage: Art. 6 Abs. 1 lit. f DSGVO. Löschung spätestens nach {P.format("Speicherdauer der Server-Protokolle, z. B. 14 Tage")}.</p>

<h2>4. TLS-Prüfung</h2>
<p>Wenn Sie eine Domain prüfen, speichern wir den Domainnamen und das Prüfergebnis. Ihre IP-Adresse speichern wir nicht im Klartext, sondern nur als verschlüsselten Hashwert (HMAC), um Missbrauch durch zu viele Anfragen zu begrenzen. Die Zählung der Anfragen wird nach 24 Stunden gelöscht. Rechtsgrundlage: Art. 6 Abs. 1 lit. b und f DSGVO.</p>

<h2>5. Reichweitenmessung ohne Cookies</h2>
<p>Für eine einfache Besucherstatistik speichern wir pro Seitenaufruf das Datum, die aufgerufene Seite, die Domain der verweisenden Website und einen täglich wechselnden Hashwert aus IP-Adresse und Browserkennung. Daraus lässt sich weder Ihre IP-Adresse ableiten noch ein Besuch über mehrere Tage verknüpfen. Es werden keine Cookies gesetzt. Speicherdauer: 180 Tage. Rechtsgrundlage: Art. 6 Abs. 1 lit. f DSGVO.</p>

<h2>6. Cookies</h2>
<p>Unsere Website setzt für Besucher keine Cookies. Nur der Betreiber erhält nach Anmeldung im Verwaltungsbereich ein technisch notwendiges Cookie. Der PayPal-Bezahlknopf (siehe Punkt 7) kann eigene Cookies setzen.</p>

<h2>7. Zahlungen über PayPal</h2>
<p>Zahlungen wickelt PayPal (Europe) S.à r.l. et Cie, S.C.A., 22-24 Boulevard Royal, L-2449 Luxemburg, ab. Auf der Ergebnis- und der Abo-Seite wird der PayPal-Bezahlknopf von Servern von PayPal geladen; dabei wird Ihre IP-Adresse an PayPal übertragen. Bei einer Zahlung übermitteln wir Betrag und Bestellreferenz. Rechtsgrundlage: Art. 6 Abs. 1 lit. b DSGVO. Datenschutzhinweise von PayPal: <a href="https://www.paypal.com/at/legalhub/privacy-full" rel="nofollow">paypal.com/at/legalhub/privacy-full</a>.</p>

<h2>7a. Zahlungen mit USDT/USDC</h2>
<p>Wenn Sie den Bericht mit einer Kryptowährung (USDT auf Polygon oder USDC auf Arbitrum) bezahlen, speichern wir die Transaktionskennung (Transaction-Hash) und den Betrag zu Ihrer Bestellung. Zur Prüfung der Zahlung fragt unser Server öffentliche Blockchain-Knoten (u. a. Allnodes/PublicNode, dRPC, Offchain Labs) nach dieser Transaktion ab; dabei wird nur die Transaktionskennung übermittelt. Rechtsgrundlage: Art. 6 Abs. 1 lit. b DSGVO. Bitte beachten Sie: Transaktionen auf einer Blockchain, einschließlich Ihrer Absenderadresse, sind öffentlich und dauerhaft einsehbar und können von uns nicht gelöscht werden. Die Zahlung geht an ein Einzahlungskonto bei einer Kryptobörse (Binance bzw. OKX).</p>

<h2>8. Überwachungs-Abonnement</h2>
<p>Für ein Abonnement speichern wir Ihre E-Mail-Adresse, den Tarif, die PayPal-Abonnement-ID, die von Ihnen eingetragenen Domains, deren Prüfergebnisse und Benachrichtigungen. Rechtsgrundlage: Art. 6 Abs. 1 lit. b DSGVO. Die Daten werden nach Vertragsende gelöscht, soweit keine gesetzlichen Aufbewahrungspflichten bestehen (Buchhaltungsunterlagen: 7 Jahre gemäß § 132 BAO).</p>
<p>Kostenlose Änderungsbenachrichtigung: Wenn Sie auf einer Ergebnisseite „Benachrichtigen“ wählen, speichern wir Ihre E-Mail-Adresse und die Domain, um diese wöchentlich zu prüfen und Sie bei Änderungen zu informieren. Rechtsgrundlage: Ihre Einwilligung (Art. 6 Abs. 1 lit. a DSGVO), bestätigt per Link (Double-Opt-in). Unbestätigte Anfragen löschen wir nach 7 Tagen. Sie können die Einwilligung jederzeit über den Link in jeder E-Mail widerrufen; Ihre Adresse wird dann sofort gelöscht.</p>

<h2>9. E-Mail-Versand</h2>
<p>E-Mails (Zugangslink, Benachrichtigungen) versenden wir über Resend, Inc., USA. Dabei werden E-Mail-Adresse und Nachrichteninhalt übermittelt. Grundlage der Übermittlung in die USA: {P.format("bitte prüfen: Zertifizierung nach dem EU-US Data Privacy Framework oder Standardvertragsklauseln")}.</p>

<h2>10. Ihre Rechte</h2>
<p>Sie haben das Recht auf Auskunft, Berichtigung, Löschung, Einschränkung der Verarbeitung, Datenübertragbarkeit und Widerspruch. Schreiben Sie dazu an {EMAIL}. Sie können sich außerdem bei der Österreichischen Datenschutzbehörde beschweren: Barichgasse 40-42, 1030 Wien, <a href="https://www.dsb.gv.at" rel="nofollow">www.dsb.gv.at</a>.</p>

<p class="muted small">Stand: November 2026</p>
""",
        },
        "en": {
            "title": "Privacy policy",
            "body": f"""
<h2>1. Controller</h2>
<p>{OWNER}, {ADDRESS_EN}, email: {EMAIL}</p>

<h2>2. Hosting</h2>
<p>The website runs on a server of The Constant Company, LLC ("Vultr", USA) in a London data centre, United Kingdom. The United Kingdom is covered by an EU Commission adequacy decision. Data processing agreement under Art. 28 GDPR: {P.format("please confirm the Vultr DPA has been accepted")}.</p>

<h2>3. Server logs</h2>
<p>For every request the server stores the IP address, date and time, requested address, referrer and browser identifier. Purpose: operating and securing the website. Legal basis: Art. 6(1)(f) GDPR. Deleted after at most {P.format("server log retention, e.g. 14 days")}.</p>

<h2>4. TLS scan</h2>
<p>When you scan a domain we store the domain name and the result. We do not store your IP address in clear text, only a keyed hash (HMAC) used to limit abuse through excessive requests. The request count is deleted after 24 hours. Legal basis: Art. 6(1)(b) and (f) GDPR.</p>

<h2>5. Cookie-free visitor statistics</h2>
<p>For simple visitor statistics we store, per page view, the date, the page, the domain of the referring website and a hash of IP address and browser identifier that changes every day. It cannot be used to recover your IP address or to link visits across days. No cookies are set. Retention: 180 days. Legal basis: Art. 6(1)(f) GDPR.</p>

<h2>6. Cookies</h2>
<p>Our website sets no cookies for visitors. Only the operator receives a technically necessary cookie after logging in to the admin area. The PayPal button (see section 7) may set its own cookies.</p>

<h2>7. Payments via PayPal</h2>
<p>Payments are processed by PayPal (Europe) S.à r.l. et Cie, S.C.A., 22-24 Boulevard Royal, L-2449 Luxembourg. On the result and subscription pages the PayPal button is loaded from PayPal's servers, which transmits your IP address to PayPal. For a payment we transmit the amount and order reference. Legal basis: Art. 6(1)(b) GDPR. PayPal's privacy notice: <a href="https://www.paypal.com/at/legalhub/privacy-full" rel="nofollow">paypal.com/at/legalhub/privacy-full</a>.</p>

<h2>7a. Payments with USDT/USDC</h2>
<p>If you pay for the report with a cryptocurrency (USDT on Polygon or USDC on Arbitrum), we store the transaction hash and amount with your order. To check the payment our server queries public blockchain nodes (including Allnodes/PublicNode, dRPC and Offchain Labs) for this transaction; only the transaction hash is transmitted. Legal basis: Art. 6(1)(b) GDPR. Please note: blockchain transactions, including your sending address, are public and permanent and cannot be deleted by us. The payment goes to a deposit account at a crypto exchange (Binance or OKX).</p>

<h2>8. Monitoring subscription</h2>
<p>For a subscription we store your email address, plan, PayPal subscription ID, the domains you add, their scan results and alerts. Legal basis: Art. 6(1)(b) GDPR. The data are deleted after the contract ends unless statutory retention applies (accounting records: 7 years under § 132 BAO).</p>
<p>Free change alert: if you choose "Notify me" on a result page, we store your email address and the domain to check it weekly and tell you about changes. Legal basis: your consent (Art. 6(1)(a) GDPR), confirmed by a link (double opt-in). Unconfirmed requests are deleted after 7 days. You can withdraw consent at any time with the link in every email; your address is then deleted immediately.</p>

<h2>9. Email delivery</h2>
<p>Emails (access link, alerts) are sent through Resend, Inc., USA, which receives the email address and message content. Basis for the transfer to the USA: {P.format("please verify: EU-US Data Privacy Framework certification or standard contractual clauses")}.</p>

<h2>10. Your rights</h2>
<p>You have the right of access, rectification, erasure, restriction of processing, data portability and objection. Write to {EMAIL}. You may also lodge a complaint with the Austrian Data Protection Authority: Barichgasse 40-42, 1030 Vienna, <a href="https://www.dsb.gv.at" rel="nofollow">www.dsb.gv.at</a>.</p>

<p class="muted small">Last updated: November 2026. In case of doubt the German version applies.</p>
""",
        },
    },
    "agb": {
        "de": {
            "title": "Allgemeine Geschäftsbedingungen (AGB)",
            "body": f"""
<h2>1. Geltungsbereich</h2>
<p>Diese AGB gelten für alle Leistungen von {OWNER} (im Folgenden „Anbieter“) über die Website ather-quantum.com.</p>

<h2>2. Leistungen</h2>
<ul>
<li><strong>Kostenlose Prüfung:</strong> Zusammenfassung der TLS-Konfiguration einer öffentlichen Domain (Note, TLS-Version, Schlüsselaustausch, Zertifikat).</li>
<li><strong>Vollständiger Bericht:</strong> einmalig 49 USD je geprüfter Domain.</li>
<li><strong>Agenturpaket:</strong> einmalig 199 USD für 10 vollständige Berichte zu frei wählbaren Domains, ohne Ablaufdatum. Jeder Bericht wird bei Nutzung eines Guthabens auf der privaten Paketseite sofort erstellt.</li>
<li><strong>Überwachung Starter:</strong> 29 USD pro Monat, bis zu 10 Domains, tägliche Prüfung und E-Mail-Benachrichtigungen.</li>
<li><strong>Überwachung Business:</strong> 99 USD pro Monat, bis zu 100 Domains, tägliche Prüfung und E-Mail-Benachrichtigungen.</li>
</ul>
<p>Die Prüfung ist eine technische Momentaufnahme von einem Messpunkt aus. Sie ersetzt kein vollständiges Sicherheitsaudit.</p>

<h2>3. Preise und Zahlung</h2>
<p>Alle Preise in US-Dollar. Gemäß § 6 Abs. 1 Z 27 UStG (Kleinunternehmerregelung) wird keine Umsatzsteuer berechnet. Die Zahlung erfolgt über PayPal (auch mit Kredit- oder Debitkarte). Den Bericht können Sie alternativ mit USDT (Netzwerk Polygon) oder USDC (Netzwerk Arbitrum One) bezahlen: Zu zahlen ist genau der angezeigte Betrag auf dem angezeigten Netzwerk; Netzwerkgebühren trägt der Absender. Für Beträge, die auf einem anderen Netzwerk, in einer anderen Währung oder an eine andere Adresse gesendet werden, können wir keine Haftung übernehmen. Eine Rückerstattung erfolgt in derselben Währung an eine vom Kunden genannte Adresse.</p>

<h2>4. Vertragsschluss</h2>
<p>Der Vertrag über den Bericht kommt mit der von PayPal bestätigten Zahlung bzw. mit der von unserem Server auf der Blockchain bestätigten Zahlung zustande. Der Abonnementvertrag kommt mit der Aktivierung des Abonnements bei PayPal zustande.</p>

<h2>5. Laufzeit und Kündigung des Abonnements</h2>
<p>Das Abonnement läuft auf unbestimmte Zeit und wird monatlich im Voraus abgerechnet. Es kann jederzeit im Kunden-Dashboard oder im PayPal-Konto gekündigt werden; die Überwachung endet mit der Kündigung, weitere Abbuchungen erfolgen nicht.</p>

<h2>6. Rücktrittsrecht für Verbraucher</h2>
<p>Verbraucher im Sinne des KSchG können von einem im Fernabsatz geschlossenen Vertrag binnen 14 Tagen ab Vertragsschluss ohne Angabe von Gründen zurücktreten (§ 11 FAGG). Die Erklärung ist an {EMAIL} zu richten. Beim <strong>vollständigen Bericht</strong> (digitaler Inhalt) erlischt das Rücktrittsrecht, wenn der Verbraucher vor der Zahlung ausdrücklich zugestimmt hat, dass der Bericht sofort bereitgestellt wird, und zur Kenntnis genommen hat, dass er dadurch sein Rücktrittsrecht verliert (§ 18 Abs. 1 Z 11 FAGG); diese Zustimmung wird beim Kauf durch ein Ankreuzfeld eingeholt und gespeichert. Beim <strong>Agenturpaket</strong> gilt dies für jeden bereits erstellten Bericht; vom Kauf noch nicht genutzter Berichte kann der Verbraucher binnen 14 Tagen zurücktreten und erhält den anteiligen Preis (19,90 USD je nicht genutztem Bericht) zurück. Beim <strong>Abonnement</strong> beginnt die Überwachung auf ausdrücklichen Wunsch des Verbrauchers sofort; bei einem Rücktritt innerhalb der Frist ist für die bis dahin erbrachten Leistungen ein anteiliges Entgelt zu zahlen (§ 16 FAGG).</p>

<h2>7. Gewährleistung und Haftung</h2>
<p>Gegenüber Verbrauchern gilt die gesetzliche Gewährleistung. Der Anbieter haftet nur für Vorsatz und grobe Fahrlässigkeit; dies gilt nicht für Personenschäden. Die Prüfergebnisse dienen der Information; für Entscheidungen auf ihrer Grundlage und für Folgeschäden wird gegenüber Unternehmern keine Haftung übernommen.</p>

<h2>8. Pflichten des Kunden</h2>
<p>Der Kunde trägt nur Domains zur Überwachung ein, an deren Prüfung er ein berechtigtes Interesse hat. Die Prüfung beschränkt sich auf gewöhnliche TLS-Verbindungsaufbauten, wie sie jeder Browser durchführt.</p>

<h2>9. Datenschutz</h2>
<p>Siehe <a href="/datenschutz?lang=de">Datenschutzerklärung</a>.</p>

<h2>10. Anwendbares Recht und Gerichtsstand</h2>
<p>Es gilt österreichisches Recht unter Ausschluss des UN-Kaufrechts und der Verweisungsnormen. Gegenüber Verbrauchern bleiben zwingende Schutzbestimmungen ihres Wohnsitzstaates unberührt. Gerichtsstand für Unternehmer ist Braunau am Inn.</p>

<p class="muted small">Stand: November 2026</p>
""",
        },
        "en": {
            "title": "Terms and conditions",
            "body": f"""
<h2>1. Scope</h2>
<p>These terms apply to all services provided by {OWNER} ("provider") through the website ather-quantum.com.</p>

<h2>2. Services</h2>
<ul>
<li><strong>Free scan:</strong> summary of the TLS configuration of a public domain (grade, TLS version, key exchange, certificate).</li>
<li><strong>Full report:</strong> one-off USD 49 per scanned domain.</li>
<li><strong>Agency pack:</strong> one-off USD 199 for 10 full reports on domains of your choice, no expiry. Each report is generated immediately when a credit is used on the private pack page.</li>
<li><strong>Monitoring Starter:</strong> USD 29 per month, up to 10 domains, daily scans and email alerts.</li>
<li><strong>Monitoring Business:</strong> USD 99 per month, up to 100 domains, daily scans and email alerts.</li>
</ul>
<p>A scan is a technical snapshot from a single vantage point. It does not replace a full security audit.</p>

<h2>3. Prices and payment</h2>
<p>All prices in US dollars. No VAT is charged under the Austrian small-business exemption (§ 6(1)(27) UStG). Payment is made through PayPal (including credit or debit card). The report can alternatively be paid with USDT (Polygon network) or USDC (Arbitrum One network): the exact amount shown must be sent on the network shown; network fees are borne by the sender. We cannot accept liability for funds sent on another network, in another token or to another address. Refunds are made in the same token to an address named by the customer.</p>

<h2>4. Conclusion of contract</h2>
<p>The contract for a report is concluded when PayPal confirms the payment, or when our server confirms the payment on the blockchain. The subscription contract is concluded when the subscription is activated at PayPal.</p>

<h2>5. Term and cancellation of the subscription</h2>
<p>The subscription runs for an indefinite period and is billed monthly in advance. It can be cancelled at any time in the customer dashboard or in the PayPal account; monitoring ends with the cancellation and no further charges are made.</p>

<h2>6. Right of withdrawal for consumers</h2>
<p>Consumers within the meaning of the Austrian Consumer Protection Act may withdraw from a distance contract within 14 days of its conclusion without giving reasons (§ 11 FAGG). The withdrawal must be sent to {EMAIL}. For the <strong>full report</strong> (digital content), the right of withdrawal expires if, before paying, the consumer expressly agreed that the report is delivered immediately and acknowledged losing the right of withdrawal (§ 18(1)(11) FAGG); this consent is collected with a checkbox at purchase and stored. For the <strong>agency pack</strong> this applies to every report already generated; the consumer may withdraw from unused reports within 14 days and receives the proportionate price back (USD 19.90 per unused report). For the <strong>subscription</strong>, monitoring starts immediately at the consumer's express request; on withdrawal within the period a proportionate amount is payable for the services provided until then (§ 16 FAGG).</p>

<h2>7. Warranty and liability</h2>
<p>Statutory warranty applies to consumers. The provider is liable only for intent and gross negligence; this does not apply to personal injury. Scan results are for information; towards businesses no liability is accepted for decisions based on them or for consequential damages.</p>

<h2>8. Customer obligations</h2>
<p>Customers add only domains they have a legitimate interest in checking. A scan consists only of ordinary TLS handshakes, as performed by any web browser.</p>

<h2>9. Data protection</h2>
<p>See the <a href="/datenschutz?lang=en">privacy policy</a>.</p>

<h2>10. Governing law and jurisdiction</h2>
<p>Austrian law applies, excluding the UN Convention on Contracts for the International Sale of Goods and conflict-of-law rules. Mandatory consumer protection rules of the consumer's country of residence remain unaffected. Place of jurisdiction for businesses: Braunau am Inn.</p>

<p class="muted small">Last updated: November 2026. In case of doubt the German version applies.</p>
""",
        },
    },
}

LANGS = ("de", "en")
