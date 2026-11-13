"""Evidence-based, free next steps; does not infer server software from TLS."""
import adoption


LIMITATION = "Observed from one location on port 443, one TLS handshake per public address; not a comprehensive security assessment, and a CDN edge may differ from the origin."


def status(result):
    kx, cert = result['key_exchange'], result['certificate']
    tls = kx.get('version') or cert.get('negotiated_version')
    if adoption.is_unsure(kx, tls):
        return 'undetermined'
    return 'observed_pq' if kx.get('pq') else 'observed_classical'


def advice(result):
    """Stable codes + observations; template translates the text, no paid findings leaked."""
    kx, cert = result['key_exchange'], result['certificate']
    items = []
    if not cert.get('verified'):
        items.append('certificate')
    elif cert.get('days_left') is not None and cert['days_left'] < 14:
        items.append('renew')
    state = status(result)
    if state == 'undetermined':
        items.append('verify')
    elif state == 'observed_pq':
        items.append('monitor')
    else:
        if (kx.get('version') or cert.get('negotiated_version')) != 'TLSv1.3':
            items.append('tls13')
        items.append('configure')
    return items


COPY = {
    'en': {
        'title': 'Recommended next steps', 'uncertainty': 'Server software and origin configuration cannot be identified from this measurement. Choose the guide for infrastructure you actually operate.',
        'certificate': 'Fix certificate validation before changing key-exchange settings.',
        'renew': 'Renew the expiring certificate and check automatic renewal.',
        'verify': 'The probe did not establish a negotiated group. Retry, then verify using a compatible TLS client; support is undetermined.',
        'monitor': 'Post-quantum exchange was observed. Monitor for configuration changes; this is not a security guarantee.',
        'tls13': 'Enable TLS 1.3 in your actual TLS stack before configuring hybrid key exchange.',
        'configure': 'Check hybrid-group support in your TLS library and configure your actual server or CDN, then repeat the measurement.',
        'limitation': LIMITATION, 'observed_pq': 'Post-quantum exchange observed', 'observed_classical': 'Classical exchange observed', 'undetermined': 'Support undetermined',
        'input_hint': 'Domain or HTTP(S) URL. HTTPS port 443 is checked; paths and pasted URL ports are not scanned.',
        'waiting': 'Scan submitted. Waiting for the server response…', 'network': 'The response could not be received. Check your connection and retry. The server may still be finishing the previous scan.',
        'invalid': 'Enter a valid domain or HTTP(S) URL without login details.', 'rate': 'Scan limit reached. Try again later.', 'failed': 'The scan could not complete. Please retry.',
        'retry': 'Retry scan', 'slow': 'Still waiting for the server. No result is available yet.',
    },
    'ar': {
        'title': 'الخطوات المقترحة', 'uncertainty': 'لا يمكن تحديد برنامج الخادم أو إعدادات الخادم الأصلي من هذا القياس. اختر الدليل المناسب للبنية التي تديرها فعليًا.',
        'certificate': 'أصلح التحقق من الشهادة قبل تغيير إعدادات تبادل المفاتيح.',
        'renew': 'جدّد الشهادة التي قاربت الانتهاء وتحقق من التجديد التلقائي.',
        'verify': 'لم يثبت المجسّ مجموعة متفاوضًا عليها. أعد المحاولة ثم تحقق بعميل TLS متوافق؛ الدعم غير محسوم.',
        'monitor': 'رُصد تبادل مفاتيح مقاوم للكم. راقب تغيّر الإعدادات؛ هذه النتيجة ليست ضمانًا أمنيًا.',
        'tls13': 'فعّل TLS 1.3 في مكتبة TLS الفعلية قبل إعداد تبادل المفاتيح الهجين.',
        'configure': 'تحقق من دعم المجموعات الهجينة في مكتبة TLS واضبط خادمك أو CDN الفعلي، ثم أعد القياس.',
        'limitation': 'رُصد من موقع واحد على المنفذ 443، بمصافحة TLS واحدة لكل عنوان عام؛ هذا ليس تقييمًا أمنيًا شاملًا، وقد تختلف واجهة CDN عن الخادم الأصلي.',
        'observed_pq': 'رُصد تبادل مقاوم للكم', 'observed_classical': 'رُصد تبادل تقليدي', 'undetermined': 'الدعم غير محسوم',
        'input_hint': 'أدخل نطاقًا أو رابط HTTP(S). يُفحص HTTPS على المنفذ 443؛ لا تُفحص المسارات أو منافذ الرابط الملصق.',
        'waiting': 'أُرسل طلب الفحص. بانتظار استجابة الخادم…', 'network': 'تعذّر استلام الاستجابة. تحقق من اتصالك ثم أعد المحاولة. قد يكون الخادم ما زال يُكمل الفحص السابق.',
        'invalid': 'أدخل نطاقًا صالحًا أو رابط HTTP(S) دون بيانات تسجيل دخول.', 'rate': 'وصلت إلى حد الفحوص. حاول لاحقًا.', 'failed': 'تعذّر إكمال الفحص. أعد المحاولة.',
        'retry': 'إعادة الفحص', 'slow': 'ما زلنا ننتظر استجابة الخادم. لا توجد نتيجة بعد.',
    },
    'de': {
        'title': 'Empfohlene nächste Schritte', 'uncertainty': 'Serversoftware und Ursprungskonfiguration sind aus dieser Messung nicht erkennbar. Wählen Sie die Anleitung für Ihre tatsächliche Infrastruktur.',
        'certificate': 'Beheben Sie zuerst die Zertifikatsprüfung.', 'renew': 'Erneuern Sie das bald ablaufende Zertifikat und prüfen Sie die automatische Erneuerung.',
        'verify': 'Die Probe konnte keine ausgehandelte Gruppe feststellen. Prüfen Sie erneut mit einem kompatiblen TLS-Client; die Unterstützung ist unbestimmt.',
        'monitor': 'Post-Quantum-Schlüsselaustausch wurde beobachtet. Überwachen Sie Änderungen; dies ist keine Sicherheitsgarantie.',
        'tls13': 'Aktivieren Sie TLS 1.3 in Ihrem tatsächlichen TLS-Stack.',
        'configure': 'Prüfen Sie hybride Gruppen in Ihrer TLS-Bibliothek und konfigurieren Sie Ihren tatsächlichen Server oder CDN. Messen Sie anschließend erneut.',
        'limitation': 'Von einem Standort auf Port 443 beobachtet, ein TLS-Handshake pro öffentlicher Adresse; keine umfassende Sicherheitsprüfung, und CDN und Ursprungsserver können sich unterscheiden.',
        'observed_pq': 'Post-Quantum-Austausch beobachtet', 'observed_classical': 'Klassischer Austausch beobachtet', 'undetermined': 'Unterstützung unbestimmt',
        'input_hint': 'Domain oder HTTP(S)-URL. Geprüft wird HTTPS auf Port 443, nicht URL-Pfade oder eingefügte Ports.',
        'waiting': 'Prüfung gesendet. Warten auf die Serverantwort…', 'network': 'Keine Antwort empfangen. Prüfen Sie Ihre Verbindung und versuchen Sie es erneut. Der Server könnte die vorherige Prüfung noch abschließen.',
        'invalid': 'Geben Sie eine gültige Domain oder HTTP(S)-URL ohne Anmeldedaten ein.', 'rate': 'Prüflimit erreicht. Bitte später erneut versuchen.', 'failed': 'Prüfung fehlgeschlagen. Bitte erneut versuchen.',
        'retry': 'Erneut prüfen', 'slow': 'Wir warten noch auf den Server. Es liegt noch kein Ergebnis vor.',
    },
}
