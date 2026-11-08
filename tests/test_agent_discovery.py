"""Agent discovery, stateless MCP interoperability and honest payment status."""
import copy
import json
import tempfile
import unittest
from unittest.mock import Mock
from urllib.robotparser import RobotFileParser

import agent_discovery
import quantum_saas_app
import quantum_vuln_scanner
from tests.test_app import RESULT


class AgentDiscoveryTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.scanner=Mock(return_value=copy.deepcopy(RESULT))
  self.app=quantum_saas_app.create_app({'TESTING':True,'DATA_DIR':self.tmp.name,'PUBLIC_URL':'https://ather-quantum.com','PAYPAL_CLIENT_ID':'','PAYPAL_CLIENT_SECRET':'','SCANS_PER_HOUR':3,'GLOBAL_SCANS_PER_HOUR':10},scanner=self.scanner)
  self.client=self.app.test_client()
 def tearDown(self):self.tmp.cleanup()
 def rpc(self,method,params=None,**kwargs):
  body={'jsonrpc':'2.0','id':1,'method':method}
  if params is not None:body['params']=params
  return self.client.post('/mcp',json=body,**kwargs)

 def test_manifest_uses_real_routes_methods_and_configured_prices(self):
  for path in ['/.well-known/agent-service.json','/api/v1/agent/discovery']:
   response=self.client.get(path);self.assertEqual(response.status_code,200);m=response.json
   self.assertEqual(m['endpoints']['scan']['url'],'https://ather-quantum.com/api/scan')
   self.assertEqual(m['endpoints']['scan']['method'],'POST')
   self.assertEqual(m['mcp']['url'],'https://ather-quantum.com/mcp')
   self.assertFalse(m['pricing']['x402']['enabled']);self.assertFalse(m['pricing']['signed_receipts']['enabled'])
   self.assertEqual(m['limits']['scan_attempts_per_client_per_hour'],3)
   self.assertEqual(m['limits']['global_scan_attempts_per_hour'],10)
   if path.startswith('/.well-known/'):
    self.assertNotIn('noindex',response.headers.get('X-Robots-Tag',''))
  self.app.config['PRICE']='57.50';self.app.config['CURRENCY']='EUR'
  price=self.client.get('/.well-known/agent-service.json').json['pricing']['full_report']
  self.assertEqual((price['amount'],price['currency']),('57.50','EUR'));self.scanner.assert_not_called()

 def test_discovery_pages_link_to_real_service_and_remain_crawlable(self):
  for lang in ['ar','en']:
   response=self.client.get('/agents?lang='+lang);self.assertEqual(response.status_code,200)
   self.assertIn('WebAPI',response.text);self.assertIn('https://ather-quantum.com/mcp',response.text)
   self.assertNotIn('<meta name="robots" content="noindex',response.text)
   self.assertIn('service-desc',response.headers.get('Link',''))
  for path in ['/llms.txt','/llms-full.txt','/openapi.yaml','/?lang=en','/?lang=ar']:
   response=self.client.get(path);self.assertEqual(response.status_code,200,path)
   self.assertIn('agent-service.json',response.text+response.headers.get('Link',''),path)
  for lang in ['ar','en']:
   self.assertIn(f'href="/business?lang={lang}"',self.client.get('/?lang='+lang).text)
  sitemap=self.client.get('/sitemap-pages.xml').text
  self.assertIn('/agents?lang=en',sitemap);self.assertIn('/agents?lang=ar',sitemap)
  self.assertIn('/agents?lang=en',self.client.get('/feed.xml').text)
  robots=RobotFileParser();robots.parse(self.client.get('/robots.txt').text.splitlines())
  for path in ['/agents','/.well-known/agent-service.json','/mcp']:
   self.assertTrue(robots.can_fetch('Googlebot','https://ather-quantum.com'+path))
  self.scanner.assert_not_called()

 def test_initialize_negotiates_supported_protocol_without_payment(self):
  for protocol in ['2025-11-25','2025-06-18','future-version']:
   response=self.rpc('initialize',{'protocolVersion':protocol,'capabilities':{},'clientInfo':{'name':'independent-buyer','version':'1.0'}})
   self.assertEqual(response.status_code,200);result=response.json['result']
   self.assertIn(result['protocolVersion'],agent_discovery.PROTOCOLS)
   self.assertEqual(result['capabilities'],{'tools':{'listChanged':False}})
   self.assertNotIn('Mcp-Session-Id',response.headers)
  self.scanner.assert_not_called()

 def test_tools_are_discoverable_and_read_only_calls_never_scan(self):
  tools=self.rpc('tools/list').json['result']['tools']
  expected={'scan_tls','get_tls_evidence','get_methodology','get_example_result','get_service_info',
            'create_full_report_order','verify_full_report_payment'}
  self.assertEqual({t['name'] for t in tools},expected)
  read_only=[t for t in tools if t.get('annotations',{}).get('readOnlyHint') is True]
  self.assertEqual({t['name'] for t in read_only},
                   {'get_tls_evidence','get_methodology','get_example_result','get_service_info'})
  self.assertEqual({t['name'] for t in tools if not t.get('annotations',{}).get('readOnlyHint')},
                   {'scan_tls','create_full_report_order','verify_full_report_payment'})
  for tool in read_only:
   arguments={'domain':'example.com'} if tool['name']=='get_tls_evidence' else {}
   response=self.rpc('tools/call',{'name':tool['name'],'arguments':arguments})
   self.assertEqual(response.status_code,200)
   self.assertFalse(response.json['result']['isError'])
   value=response.json['result']['structuredContent']
   self.assertEqual(json.loads(response.json['result']['content'][0]['text']),value)
  self.scanner.assert_not_called()

 def test_live_scan_reuses_api_summary_and_existing_limits(self):
  self.app.config['SCANS_PER_HOUR']=1
  first=self.rpc('tools/call',{'name':'scan_tls','arguments':{'domain':'example.com'}})
  self.assertFalse(first.json['result']['isError']);data=first.json['result']['structuredContent']
  self.assertEqual(data['domain'],'example.com');self.assertEqual(data['observation_status'],'observed_classical')
  self.assertEqual(self.client.get('/api/scan/'+data['scan_id']).json,data)
  with self.app.app_context():
   source=quantum_saas_app.db().execute('SELECT source FROM scans WHERE id=?',(data['scan_id'],)).fetchone()['source']
  self.assertEqual(source,'mcp')
  second=self.rpc('tools/call',{'name':'scan_tls','arguments':{'domain':'example.com'}})
  self.assertTrue(second.json['result']['isError'])
  self.assertEqual(second.json['result']['structuredContent']['http_status'],429)
  api=self.client.post('/api/scan',json={'domain':'example.com'});self.assertEqual(api.status_code,429)
  self.scanner.assert_called_once_with('example.com')

 def test_methodology_and_archived_example_are_explicit(self):
  method=self.client.get('/api/v1/agent/methodology').json
  self.assertEqual(set(method['observation_states']),{'observed_pq','observed_classical','undetermined'})
  self.assertIn('HSTS measurement',method['not_provided'])
  sample=self.client.get('/api/v1/agent/example').json
  self.assertTrue(sample['is_example']);self.assertFalse(sample['is_live'])
  self.assertIsNone(sample['scan_id']);self.assertIn('/sample-report',sample['scan_url'])
  self.assertNotIn('score',sample);self.assertNotIn('safe_to_execute',sample);self.scanner.assert_not_called()

 def test_rpc_rejects_bad_arguments_without_executing_scan(self):
  for params in [{'name':'unknown','arguments':{}},{'name':'scan_tls','arguments':[]},{'name':'scan_tls','arguments':{}},{'name':'scan_tls','arguments':{'domain':'example.com','pay':True}},{'name':'get_methodology','arguments':{'domain':'example.com'}},{'name':[],'arguments':{}}]:
   response=self.rpc('tools/call',params);self.assertEqual(response.status_code,400)
   self.assertEqual(response.json['error']['code'],-32602)
  invalid=self.rpc('tools/call',{'name':'scan_tls','arguments':{'domain':'127.0.0.1'}})
  self.assertTrue(invalid.json['result']['isError']);self.scanner.assert_not_called()

 def test_origin_protocol_content_type_and_notifications(self):
  bad=self.rpc('ping',headers={'Origin':'https://evil.example'})
  self.assertEqual(bad.status_code,403)
  good=self.rpc('ping',headers={'Origin':'https://ather-quantum.com'})
  self.assertEqual(good.status_code,200)
  version=self.rpc('ping',headers={'MCP-Protocol-Version':'unsupported'})
  self.assertEqual(version.status_code,400)
  self.assertEqual(self.client.get('/mcp').status_code,405)
  self.assertEqual(self.client.post('/mcp',data='{}',content_type='text/plain').status_code,415)
  malformed=self.client.post('/mcp',data='{',content_type='application/json')
  self.assertEqual(malformed.json['error']['code'],-32700)
  self.assertEqual(self.client.post('/mcp',json=[]).status_code,400)
  notification=self.client.post('/mcp',json={'jsonrpc':'2.0','method':'notifications/initialized'})
  self.assertEqual(notification.status_code,202);self.assertEqual(notification.data,b'')
  notification=self.client.post('/mcp',json={'jsonrpc':'2.0','method':'tools/call','params':{'name':'scan_tls','arguments':{'domain':'example.com'}}})
  self.assertEqual(notification.status_code,202);self.scanner.assert_not_called()

 def test_tool_scan_errors_preserve_undetermined_and_do_not_expose_secrets(self):
  self.scanner.side_effect=quantum_vuln_scanner.ScanError('tls_failure','Probe failed')
  response=self.rpc('tools/call',{'name':'scan_tls','arguments':{'domain':'example.com'}})
  self.assertTrue(response.json['result']['isError'])
  self.assertEqual(response.json['result']['structuredContent']['error'],'tls_failure')

 def test_registry_metadata_describes_real_remote_transport(self):
  data=self.client.get('/api/v1/agent/mcp-server.json').json
  self.assertEqual(data['remotes'],[{'type':'streamable-http','url':'https://ather-quantum.com/mcp'}])
  self.assertEqual(data['name'],'io.github.moncef00327-cloud/quantum-aether')
