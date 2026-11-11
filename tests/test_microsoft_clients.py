"""Microsoft Copilot Studio / Security Copilot: protocol 2025-03-26 and the Security Copilot plugin manifest."""
import copy
import tempfile
import unittest
from unittest.mock import Mock

import agent_discovery
import quantum_saas_app
from tests.test_app import RESULT

BASE = 'https://ather-quantum.com'


class MicrosoftClientTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.scanner = Mock(return_value=copy.deepcopy(RESULT))
        self.app = quantum_saas_app.create_app({'TESTING': True, 'DATA_DIR': self.tmp.name, 'PUBLIC_URL': BASE,
                                                'PAYPAL_CLIENT_ID': '', 'PAYPAL_CLIENT_SECRET': ''}, scanner=self.scanner)
        self.client = self.app.test_client()

    def tearDown(self):
        self.tmp.cleanup()

    def test_streamable_http_2025_03_26_client_gets_its_version(self):
        r = self.client.post('/mcp', json={'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {
            'protocolVersion': '2025-03-26', 'capabilities': {}, 'clientInfo': {'name': 'copilot', 'version': '1'}}})
        self.assertEqual(r.json['result']['protocolVersion'], '2025-03-26')
        r = self.client.post('/mcp', json={'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'},
                             headers={'MCP-Protocol-Version': '2025-03-26'})
        self.assertEqual(r.status_code, 200)
        self.assertIn('scan_tls', [t['name'] for t in r.json['result']['tools']])
        self.scanner.assert_not_called()

    def test_security_copilot_manifest(self):
        r = self.client.get('/security-copilot.yaml')
        self.assertEqual(r.status_code, 200)
        self.assertIn('yaml', r.headers['Content-Type'])
        body = r.get_data(as_text=True)
        self.assertIn(f'Endpoint: {BASE}/mcp', body)
        self.assertIn('Format: MCP', body)
        self.assertIn('UseStreamableHttp: true', body)
        allowed = body.split('AllowedTools:')[1].strip().split(',')
        tools = {t['name']: t for t in agent_discovery.TOOLS}
        for name in allowed:
            with self.subTest(tool=name):
                self.assertIn(name, tools)
                self.assertFalse(tools[name]['annotations'].get('destructiveHint', False))
                for prop in tools[name]['inputSchema'].get('properties', {}).values():
                    self.assertIn(prop['type'], ('string', 'boolean', 'integer', 'number'))
        for paid in ('get_full_report', 'create_full_report_order', 'verify_full_report_payment'):
            self.assertNotIn(paid, allowed)
        self.assertNotIn('\t', body)

    def test_agents_page_explains_both_products(self):
        for lang, needle in (('en', 'Use it in Microsoft Copilot Studio and Security Copilot'),
                             ('ar', 'استخدمه في Microsoft Copilot Studio وSecurity Copilot')):
            html = self.client.get(f'/agents?lang={lang}').get_data(as_text=True)
            self.assertIn(needle, html)
            self.assertIn(f'{BASE}/security-copilot.yaml', html)
            self.assertIn(f'{BASE}/mcp', html)


if __name__ == '__main__':
    unittest.main()
