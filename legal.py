# legal.py
# الصفحات القانونية للنمسا (Impressum، Datenschutz، AGB) بالألمانية والإنجليزية.
# كل بيان شخصي أو تجاري غير معروف بعد مكتوب كخانة [بين قوسين] ليملأها صاحب الموقع.
# المحتوى HTML مكتوب هنا يدوياً، لا يأتي من المستخدم.

P = '<mark class="placeholder">[{}]</mark>'
OWNER = "Omer Alsaloum"
ADDRESS = P.format("Straßenname") + " 11/12, 5280 Braunau am Inn, Österreich"
ADDRESS_EN = P.format("street name") + " 11/12, 5280 Braunau am Inn, Austria"
EMAIL = '<a href="mailto:sajad.vip56@gmail.com">sajad.vip56@gmail.com</a>'

PAGES = {
    "impressum": {
        "de": {
            "title": "Impressum",
            "body": f"""
<p>Angaben gemäß § 5 E-Commerce-Gesetz (ECG), § 14 Unternehmensgesetzbuch (UGB), § 63 Gewerbeordnung (GewO) und Offenlegung gemäß § 25 Mediengesetz (MedienG).</p>
<h2>Medieninhaber und Diensteanbieter</h2>
<p>{OWNER}<br>{ADDRESS}</p>
<p>E-Mail: {EMAIL}<br>Telefon: {P.format("Telefonnummer (optional)")}</p>
<h2>Unternehmensangaben</h2>
<ul>
<li>Unternehmensgegenstand: IT-Dienstleistungen; Betrieb eines Online-Dienstes zur Prüfung der Post-Quanten-Bereitschaft von TLS-Verbindungen</li>
<li>UID-Nummer: {P.format("UID-Nummer, falls vorhanden")}</li>
<li>Firmenbuchnummer und Firmenbuchgericht: {P.format("falls im Firmenbuch eingetragen")}</li>
<li>Gewerbebehörde: {P.format("zuständige Bezirkshauptmannschaft bzw. Magistrat")}</li>
<li>Kammerzugehörigkeit: {P.format("Wirtschaftskammer / Landeskammer, falls Gewerbe angemeldet")}</li>
<li>Anwendbare berufsrechtliche Vorschriften: Gewerbeordnung, abrufbar unter <a href="https://www.ris.bka.gv.at" rel="nofollow">www.ris.bka.gv.at</a></li>
</ul>
<h2>Blattlinie (§ 25 Abs. 4 MedienG)</h2>
<p>Information über Post-Quanten-Kryptographie und TLS-Sicherheit sowie Angebot eines Prüf- und Überwachungsdienstes.</p>
""",
        },
        "en": {
            "title": "Imprint (Impressum)",
            "body": f"""
<p>Information pursuant to § 5 Austrian E-Commerce Act (ECG), § 14 Austrian Commercial Code (UGB), § 63 Trade Act (GewO) and disclosure pursuant to § 25 Media Act (MedienG).</p>
<h2>Media owner and service provider</h2>
<p>{OWNER}<br>{ADDRESS_EN}</p>
<p>Email: {EMAIL}<br>Phone: {P.format("Phone number (optional)")}</p>
<h2>Business details</h2>
<ul>
<li>Business purpose: IT services; operation of an online service that checks the post-quantum readiness of TLS connections</li>
<li>VAT ID (UID): {P.format("VAT ID, if any")}</li>
<li>Company register number and court: {P.format("if registered in the Firmenbuch")}</li>
<li>Supervisory trade authority: {P.format("competent district authority or municipal office")}</li>
<li>Chamber membership: {P.format("Austrian Economic Chamber / regional chamber, if a trade is registered")}</li>
<li>Applicable professional regulations: Austrian Trade Act (Gewerbeordnung), available at <a href="https://www.ris.bka.gv.at" rel="nofollow">www.ris.bka.gv.at</a></li>
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

<h2>8. Überwachungs-Abonnement</h2>
<p>Für ein Abonnement speichern wir Ihre E-Mail-Adresse, den Tarif, die PayPal-Abonnement-ID, die von Ihnen eingetragenen Domains, deren Prüfergebnisse und Benachrichtigungen. Rechtsgrundlage: Art. 6 Abs. 1 lit. b DSGVO. Die Daten werden nach Vertragsende gelöscht, soweit keine gesetzlichen Aufbewahrungspflichten bestehen (Buchhaltungsunterlagen: 7 Jahre gemäß § 132 BAO).</p>

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

<h2>8. Monitoring subscription</h2>
<p>For a subscription we store your email address, plan, PayPal subscription ID, the domains you add, their scan results and alerts. Legal basis: Art. 6(1)(b) GDPR. The data are deleted after the contract ends unless statutory retention applies (accounting records: 7 years under § 132 BAO).</p>

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
<p>Diese AGB gelten für alle Leistungen von {OWNER} (im Folgenden „Anbieter“) über die Website ather-quatum.cloud.</p>

<h2>2. Leistungen</h2>
<ul>
<li><strong>Kostenlose Prüfung:</strong> Zusammenfassung der TLS-Konfiguration einer öffentlichen Domain (Note, TLS-Version, Schlüsselaustausch, Zertifikat).</li>
<li><strong>Vollständiger Bericht:</strong> einmalig 49 USD je geprüfter Domain.</li>
<li><strong>Überwachung Starter:</strong> 29 USD pro Monat, bis zu 10 Domains, tägliche Prüfung und E-Mail-Benachrichtigungen.</li>
<li><strong>Überwachung Business:</strong> 99 USD pro Monat, bis zu 100 Domains, tägliche Prüfung und E-Mail-Benachrichtigungen.</li>
</ul>
<p>Die Prüfung ist eine technische Momentaufnahme von einem Messpunkt aus. Sie ersetzt kein vollständiges Sicherheitsaudit.</p>

<h2>3. Preise und Zahlung</h2>
<p>Alle Preise in US-Dollar. {P.format("Umsatzsteuer-Hinweis, z. B. „inkl. 20 % USt.“ oder „Kleinunternehmer gemäß § 6 Abs. 1 Z 27 UStG, keine USt.“")}. Die Zahlung erfolgt über PayPal (auch mit Kredit- oder Debitkarte).</p>

<h2>4. Vertragsschluss</h2>
<p>Der Vertrag über den Bericht kommt mit der von PayPal bestätigten Zahlung zustande. Der Abonnementvertrag kommt mit der Aktivierung des Abonnements bei PayPal zustande.</p>

<h2>5. Laufzeit und Kündigung des Abonnements</h2>
<p>Das Abonnement läuft auf unbestimmte Zeit und wird monatlich im Voraus abgerechnet. Es kann jederzeit im Kunden-Dashboard oder im PayPal-Konto gekündigt werden; die Überwachung endet mit der Kündigung, weitere Abbuchungen erfolgen nicht.</p>

<h2>6. Rücktrittsrecht für Verbraucher</h2>
<p>Verbraucher im Sinne des KSchG können von einem im Fernabsatz geschlossenen Vertrag binnen 14 Tagen ab Vertragsschluss ohne Angabe von Gründen zurücktreten (§ 11 FAGG). Die Erklärung ist an {EMAIL} zu richten. Beim <strong>vollständigen Bericht</strong> (digitaler Inhalt) erlischt das Rücktrittsrecht, wenn der Verbraucher vor der Zahlung ausdrücklich zugestimmt hat, dass der Bericht sofort bereitgestellt wird, und zur Kenntnis genommen hat, dass er dadurch sein Rücktrittsrecht verliert (§ 18 Abs. 1 Z 11 FAGG); diese Zustimmung wird beim Kauf durch ein Ankreuzfeld eingeholt und gespeichert. Beim <strong>Abonnement</strong> beginnt die Überwachung auf ausdrücklichen Wunsch des Verbrauchers sofort; bei einem Rücktritt innerhalb der Frist ist für die bis dahin erbrachten Leistungen ein anteiliges Entgelt zu zahlen (§ 16 FAGG).</p>

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
<p>These terms apply to all services provided by {OWNER} ("provider") through the website ather-quatum.cloud.</p>

<h2>2. Services</h2>
<ul>
<li><strong>Free scan:</strong> summary of the TLS configuration of a public domain (grade, TLS version, key exchange, certificate).</li>
<li><strong>Full report:</strong> one-off USD 49 per scanned domain.</li>
<li><strong>Monitoring Starter:</strong> USD 29 per month, up to 10 domains, daily scans and email alerts.</li>
<li><strong>Monitoring Business:</strong> USD 99 per month, up to 100 domains, daily scans and email alerts.</li>
</ul>
<p>A scan is a technical snapshot from a single vantage point. It does not replace a full security audit.</p>

<h2>3. Prices and payment</h2>
<p>All prices in US dollars. {P.format("VAT note, e.g. 'incl. 20% VAT' or 'small business under § 6(1)(27) UStG, no VAT charged'")}. Payment is made through PayPal (including credit or debit card).</p>

<h2>4. Conclusion of contract</h2>
<p>The contract for a report is concluded when PayPal confirms the payment. The subscription contract is concluded when the subscription is activated at PayPal.</p>

<h2>5. Term and cancellation of the subscription</h2>
<p>The subscription runs for an indefinite period and is billed monthly in advance. It can be cancelled at any time in the customer dashboard or in the PayPal account; monitoring ends with the cancellation and no further charges are made.</p>

<h2>6. Right of withdrawal for consumers</h2>
<p>Consumers within the meaning of the Austrian Consumer Protection Act may withdraw from a distance contract within 14 days of its conclusion without giving reasons (§ 11 FAGG). The withdrawal must be sent to {EMAIL}. For the <strong>full report</strong> (digital content), the right of withdrawal expires if, before paying, the consumer expressly agreed that the report is delivered immediately and acknowledged losing the right of withdrawal (§ 18(1)(11) FAGG); this consent is collected with a checkbox at purchase and stored. For the <strong>subscription</strong>, monitoring starts immediately at the consumer's express request; on withdrawal within the period a proportionate amount is payable for the services provided until then (§ 16 FAGG).</p>

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
