import tempfile
import unittest

import quantum_saas_app
import radar
import sales_db


class GravityWebTests(unittest.TestCase):
    def test_empty_dashboard_and_real_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            app = quantum_saas_app.create_app({'TESTING': True, 'DATA_DIR': directory})
            client = app.test_client()
            response = client.get('/gravity?lang=ar')
            self.assertEqual(response.status_code, 200)
            self.assertIn('بانتظار أدلة كافية', response.get_data(as_text=True))
            conn = sales_db.connect(directory + '/quantum_saas.db')
            try:
                radar.init(conn)
                conn.execute("INSERT INTO radar_seen VALUES (?, ?, ?, ?, datetime('now'))",
                             ('https://github.com/a/b/issues/1', 'GitHub',
                              'How to enable X25519MLKEM768 on nginx TLS?', 'nginx'))
                conn.commit()
            finally:
                conn.close()
            response = client.get('/gravity?lang=en')
            self.assertEqual(response.status_code, 200)
            self.assertIn('https://github.com/a/b/issues/1', response.get_data(as_text=True))
            self.assertNotIn('Waiting for qualifying evidence', response.get_data(as_text=True))
            self.assertIn('noindex', response.headers.get('X-Robots-Tag', ''))
            self.assertNotIn('/gravity', client.get('/sitemap-pages.xml').get_data(as_text=True))
            self.assertNotIn('/gravity', client.get('/guides?lang=en').get_data(as_text=True))
