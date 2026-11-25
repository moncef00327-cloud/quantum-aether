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
   self.assertFalse(m['pricing']['x402']['enabled']);self.assertEqual(m['pricing']['x402']['status'],'disabled_missing_receiver')
   self.assertIn('get_full_report',m['mcp']['tools']);self.assertTrue(m['pricing']['signed_receipts']['enabled'])
   self.assertEqual(m['pricing']['signed_receipts']['jwks_uri'],'https://ather-quantum.com/.well-known/jwks.json')
   self.assertEqual(m['limits']['scan_attempts_per_client_per_hour'],3)
   self.assertEqual(m['limits']['global_scan_attempts_per_hour'],10)
   if path.startswith('/.well-known/'):
    self.assertNotIn('noindex',response.headers.get('X-Robots-Tag',''))
  self.app.config['PRICE']='57.50';self.app.config['CURRENCY']='EUR'
  price=self.client.get('/.well-known/agent-service.json').json['pricing']['full_report']
  self.assertEqual((price['amount'],price['currency']),('57.50','EUR'));self.scanner.assert_not_called()

 def test_manifest_reports_configured_x402_truthfully(self):
  self.app.config['USDC_BASE_ADDR']='0x'+'44'*20
  manifest=self.client.get('/.well-known/agent-service.json').json
  self.assertTrue(manifest['pricing']['x402']['enabled'])
  self.assertEqual(manifest['pricing']['x402']['status'],'configured')
  self.assertTrue(manifest['pricing']['x402']['buyer_wallet_required'])
  self.assertEqual(manifest['pricing']['full_report']['mcp_tool'],'get_full_report')
  self.assertIn('Not listed',manifest['directory_status']['x402_bazaar'])

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
  self.assertFalse(robots.can_fetch('Googlebot','https://ather-quantum.com/badge/example.com.svg'))  # crawl budget
  self.assertTrue(robots.can_fetch('Googlebot','https://ather-quantum.com/guides'))
  self.scanner.assert_not_called()

 def test_initialize_negotiates_supported_protocol_without_payment(self):
  for protocol in ['2025-11-25','2025-06-18','future-version']:
   response=self.rpc('initialize',{'protocolVersion':protocol,'capabilities':{},'clientInfo':{'name':'independent-buyer','version':'1.0'}})
   self.assertEqual(response.status_code,200);result=response.json['result']
   self.assertIn(result['protocolVersion'],agent_discovery.PROTOCOLS)
   self.assertEqual(result['capabilities'],{'tools':{'listChanged':False},'resources':{'subscribe':False,'listChanged':False},'prompts':{'listChanged':False}})
   self.assertIn('get_full_report',result['instructions'])
   self.assertIn('generate_pq_config',result['instructions'])
   self.assertNotIn('Mcp-Session-Id',response.headers)
  self.scanner.assert_not_called()

 def test_tools_are_discoverable_and_read_only_calls_never_scan(self):
  tools=self.rpc('tools/list').json['result']['tools']
  expected={'scan_tls','get_tls_evidence','exposure_window','get_methodology','get_example_result','get_service_info','generate_pq_config','get_full_report','get_sector_snapshot','get_tls_attestation',
            'create_full_report_order','verify_full_report_payment','register_agent_affiliate'}
  self.assertEqual({t['name'] for t in tools},expected)
  paid=next(t for t in tools if t['name']=='get_full_report')['description']
  self.assertIn('x402',paid);self.assertIn('$'+str(self.app.config['PRICE'])+' USDC',paid);self.assertNotIn('{price}',paid)
  read_only=[t for t in tools if t.get('annotations',{}).get('readOnlyHint') is True]
  self.assertEqual({t['name'] for t in read_only},
                   {'get_tls_evidence','exposure_window','get_methodology','get_example_result','get_service_info','generate_pq_config','get_sector_snapshot'})
  self.assertEqual({t['name'] for t in tools if not t.get('annotations',{}).get('readOnlyHint')},
                   {'scan_tls','get_full_report','get_tls_attestation','create_full_report_order','verify_full_report_payment','register_agent_affiliate'})
  for tool in read_only:
   if tool['name']=='get_sector_snapshot':continue  # paid read-only: returns an x402 challenge (tests/test_x402_sector.py)
   if tool['name'] in ('get_tls_evidence','exposure_window'):arguments={'domain':'example.com'}
   elif tool['name']=='generate_pq_config':arguments={'server':'nginx'}
   else:arguments={}
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
  api_summary=self.client.get('/api/scan/'+data['scan_id']).json
  for k,v in api_summary.items():self.assertEqual(data[k],v)
  self.assertIn('signed_receipt_jws',data);self.assertIn('receipt',data);self.assertIn('verify',data)
  with self.app.app_context():
   source=quantum_saas_app.db().execute('SELECT source FROM scans WHERE id=?',(data['scan_id'],)).fetchone()['source']
  self.assertEqual(source,'mcp')
  second=self.rpc('tools/call',{'name':'scan_tls','arguments':{'domain':'example.com'}})
  self.assertFalse(second.json['result']['isError'])  # useful answer, not an empty refusal
  self.assertEqual(second.json['result']['structuredContent']['http_status'],429)
  self.assertEqual(second.json['result']['structuredContent']['stored_evidence']['domain'],'example.com')
  api=self.client.post('/api/scan',json={'domain':'example.com'});self.assertEqual(api.status_code,429)
  self.scanner.assert_called_once_with('example.com')

 def test_paid_mcp_tool_exposes_x402_challenge_then_unlocks_report(self):
  self.app.config['USDC_BASE_ADDR']='0x'+'44'*20
  scan_id=self.client.post('/api/scan',json={'domain':'example.com'}).json['scan_id']
  call=lambda meta=None:self.rpc('tools/call',{'name':'get_full_report','arguments':{'scan_id':scan_id},**({'_meta':meta} if meta else {})})
  challenge_response=call()
  self.assertEqual(challenge_response.status_code,200)
  tool_result=challenge_response.json['result']
  self.assertTrue(tool_result['isError'])
  challenge=tool_result['structuredContent']
  self.assertEqual(json.loads(tool_result['content'][0]['text']),challenge)
  accepted=challenge['accepts'][0]
  self.assertEqual(accepted['network'],'eip155:8453')
  self.assertEqual(accepted['asset'].lower(),'0x833589fcd6edb6e08f4c7c32d4f71b54bda02913')
  self.assertEqual(accepted['payTo'].lower(),self.app.config['USDC_BASE_ADDR'])
  payload={'x402Version':2,'resource':challenge['resource'],'accepted':accepted}
  import quantum_saas_app
  verified=Mock();verified.raise_for_status.return_value=None;verified.json.return_value={'isValid':True}
  settled=Mock();settled.json.return_value={'success':True,'transaction':'0x'+'ab'*32,'network':'eip155:8453'}
  from unittest.mock import patch
  with patch('quantum_saas_app.requests.post',side_effect=[verified,settled]) as facilitator:
   paid=call({'x402/payment':payload})
  self.assertFalse(paid.json['result']['isError'])
  report=paid.json['result']['structuredContent']
  self.assertEqual(report['status'],'COMPLETED')
  self.assertIn('/report/',report['report_url'])
  self.assertEqual(paid.json['result']['_meta']['x402/payment-response']['transaction'],'0x'+'ab'*32)
  self.assertEqual(facilitator.call_count,2)
  self.assertEqual(self.client.get(report['report_url'].replace('https://ather-quantum.com','')).status_code,200)

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
  for path in ['/api/v1/agent/mcp-server.json','/.well-known/mcp.json']:
   data=self.client.get(path).json
   self.assertEqual(data['remotes'],[{'type':'streamable-http','url':'https://ather-quantum.com/mcp'}])
   self.assertEqual(data['name'],'io.github.moncef00327-cloud/quantum-aether')
  plugin=self.client.get('/.well-known/ai-plugin.json').json
  self.assertEqual(plugin['api']['url'],'https://ather-quantum.com/openapi.yaml')
  self.assertEqual(plugin['mcp']['url'],'https://ather-quantum.com/mcp')
  self.assertEqual(plugin['partner_affiliate']['mcp_tool'],'register_agent_affiliate')
  self.assertEqual(plugin['partner_affiliate']['payout_schedule'],'monthly_manual_by_owner')

 def test_well_known_server_card_api_catalog_and_agents_json(self):
  for path in ('/.well-known/mcp/server-card.json','/mcp/server-card'):
   card=self.client.get(path)
   self.assertEqual(card.status_code,200,path)
   self.assertEqual(card.headers.get('Access-Control-Allow-Origin'),'*')
   cj=card.json
   self.assertEqual(cj['transport']['endpoint'],'https://ather-quantum.com/mcp')
   self.assertIn('register_agent_affiliate',{t['name'] for t in cj['tools']})
   self.assertEqual(cj['partner_affiliate']['monitoring_commission_pct'],30)

  cat=self.client.get('/.well-known/api-catalog')
  self.assertEqual(cat.status_code,200)
  self.assertIn('application/linkset+json',cat.content_type)
  anchors={item['anchor'] for item in cat.json['linkset']}
  self.assertIn('https://ather-quantum.com/mcp',anchors)
  self.assertIn('https://ather-quantum.com/api/v1/agent/affiliate/register',anchors)

  ai_cat=self.client.get('/.well-known/ai-catalog.json')
  self.assertEqual(ai_cat.status_code,200)
  self.assertEqual(ai_cat.headers.get('Access-Control-Allow-Origin'),'*')

  glama=self.client.get('/.well-known/glama.json')
  self.assertEqual(glama.status_code,200)
  self.assertEqual(glama.headers.get('Access-Control-Allow-Origin'),'*')
  self.assertIn('moncef00327-cloud',glama.json['maintainers'])

  for method,key in (('resources/list','resources'),('resources/templates/list','resourceTemplates'),('prompts/list','prompts')):
   r=self.rpc(method)
   self.assertEqual(r.status_code,200,method)
   self.assertTrue(r.json['result'][key],method)
  unknown=self.rpc('nonexistent/method')
  self.assertEqual(unknown.status_code,404)
  self.assertEqual(unknown.json['error']['code'],-32601)

  aj=self.client.get('/.well-known/agents.json')
  self.assertEqual(aj.status_code,200)
  flows={f['id'] for f in aj.json['flows']}
  self.assertEqual(flows,{'scan_tls_signed_receipt','read_stored_tls_evidence','register_agent_affiliate'})

  link=self.client.get('/partners?lang=en').headers.get('Link','')
  self.assertIn('rel="api-catalog"',link)
  self.assertIn('rel="mcp-server-card"',link)
  self.assertIn('rel="agents-json"',link)

  oa=self.client.get('/openapi.yaml').text
  self.assertIn('/api/v1/agent/affiliate/register:',oa)
  self.assertIn('/.well-known/mcp/server-card.json:',oa)
  self.assertNotIn('No automatic payments or signed receipts are implemented',oa)

 def test_free_mcp_endpoint_lists_only_free_tools_with_explicit_hints(self):
  r=self.client.post('/mcp/free',json={'jsonrpc':'2.0','id':1,'method':'tools/list'}).json['result']['tools']
  self.assertEqual({t['name'] for t in r},agent_discovery.FREE_TOOLS)
  for t in r:
   self.assertTrue(t['title'])
   for k in ('readOnlyHint','destructiveHint','openWorldHint'):self.assertIsInstance(t['annotations'][k],bool,(t['name'],k))
  paid=self.client.post('/mcp/free',json={'jsonrpc':'2.0','id':2,'method':'tools/call','params':{'name':'get_full_report','arguments':{'scan_id':'x'}}}).json
  self.assertEqual(paid['error']['code'],-32602)
  init=self.client.post('/mcp/free',json={'jsonrpc':'2.0','id':3,'method':'initialize','params':{'protocolVersion':'2025-06-18','capabilities':{},'clientInfo':{'name':'t','version':'1'}}}).json
  self.assertIn('Free tools only',init['result']['instructions'])
  full=self.client.post('/mcp',json={'jsonrpc':'2.0','id':4,'method':'tools/list'}).json['result']['tools']
  self.assertIn('get_sector_snapshot',{t['name'] for t in full})

 def test_mcp_scan_includes_human_and_x402_conversion_next_steps(self):
  res=self.client.post('/mcp',json={'jsonrpc':'2.0','id':10,'method':'tools/call','params':{'name':'scan_tls','arguments':{'domain':'example.com'}}}).json['result']
  sc=res['structuredContent']
  steps=sc['recommended_next_steps']
  self.assertIn('/monitoring?domain=example.com#trial-form',steps['monitoring_trial']['url'])
  self.assertIn('/api/v1/attestation/sample.pdf',steps['sample_auditor_pdf']['url'])
  self.assertIn('/scan/',steps['full_report_checkout']['url'])
  self.assertEqual(steps['x402_attestation']['mcp_tool'],'get_tls_attestation')
  self.assertIn('Next steps:',res['content'][0]['text'])

  # /mcp/free keeps human links but omits x402 payment tools
  res_free=self.client.post('/mcp/free',json={'jsonrpc':'2.0','id':11,'method':'tools/call','params':{'name':'get_tls_evidence','arguments':{'domain':'example.com'}}}).json['result']
  steps_free=res_free['structuredContent']['recommended_next_steps']
  self.assertIn('monitoring_trial',steps_free)
  self.assertNotIn('x402_attestation',steps_free)

 def test_generate_pq_config_tool_and_validation(self):
  res=self.rpc('tools/call',{'name':'generate_pq_config','arguments':{'server':'nginx','lang':'de'}}).json['result']
  self.assertFalse(res['isError'])
  sc=res['structuredContent']
  self.assertEqual(sc['server'],'nginx')
  self.assertEqual(sc['lang'],'de')
  self.assertTrue(sc['ready'])
  self.assertIn('X25519MLKEM768',json.dumps(sc['steps']))
  self.assertIn('/partners',sc['recommended_next_steps']['msp_pilot']['url'])
  # Also works on /mcp/free without x402 links
  res_free=self.client.post('/mcp/free',json={'jsonrpc':'2.0','id':12,'method':'tools/call','params':{'name':'generate_pq_config','arguments':{'server':'cloudflare','lang':'ar'}}}).json['result']
  self.assertFalse(res_free['isError'])
  self.assertNotIn('x402_attestation',res_free['structuredContent']['recommended_next_steps'])
  # Invalid server rejected with -32602
  bad=self.rpc('tools/call',{'name':'generate_pq_config','arguments':{'server':'invalid-server'}}).json
  self.assertEqual(bad['error']['code'],-32602)
  self.scanner.assert_not_called()

 def test_mcp_resources_and_prompts_full_lifecycle(self):
  res_list=self.rpc('resources/list').json['result']['resources']
  uris={r['uri'] for r in res_list}
  self.assertTrue({'qa://methodology','qa://policy/qa-pqc-transport/1.0','qa://deadlines/pqc','qa://msp-pilot','qa://pricing'}<=uris)
  for uri in list(uris)+['qa://config/nginx','qa://evidence/example.com']:
   rr=self.rpc('resources/read',{'uri':uri})
   self.assertEqual(rr.status_code,200,uri)
   contents=rr.json['result']['contents']
   self.assertEqual(contents[0]['uri'],uri)
   self.assertEqual(contents[0]['mimeType'],'application/json')
   parsed=json.loads(contents[0]['text'])
   self.assertIsInstance(parsed,dict)
  missing=self.rpc('resources/read',{'uri':'qa://does-not-exist'}).json
  self.assertEqual(missing['error']['code'],-32002)

  plist=self.rpc('prompts/list').json['result']['prompts']
  pnames={p['name'] for p in plist}
  self.assertEqual(pnames,{'audit_domain_pqc','generate_pqc_remediation','msp_pilot_assessment','verify_tls_receipt'})
  p1=self.rpc('prompts/get',{'name':'audit_domain_pqc','arguments':{'domain':'example.com','framework':'BSI TR-02102-2'}}).json['result']
  self.assertIn('example.com',p1['messages'][0]['content']['text'])
  self.assertIn('generate_pq_config',p1['messages'][0]['content']['text'])
  p2=self.rpc('prompts/get',{'name':'msp_pilot_assessment','arguments':{'lang':'de'}}).json['result']
  self.assertIn('290 EUR',p2['messages'][0]['content']['text'])
  p3=self.rpc('prompts/get',{'name':'generate_pqc_remediation','arguments':{'server':'caddy'}}).json['result']
  self.assertIn('caddy',p3['messages'][0]['content']['text'])
  p4=self.rpc('prompts/get',{'name':'verify_tls_receipt','arguments':{'target_or_jti':'rcpt_123'}}).json['result']
  self.assertIn('rcpt_123',p4['messages'][0]['content']['text'])
  bad_p=self.rpc('prompts/get',{'name':'audit_domain_pqc','arguments':{}}).json
  self.assertEqual(bad_p['error']['code'],-32602)

  card=self.client.get('/.well-known/mcp/server-card.json').json
  self.assertTrue(card['capabilities']['resources'])
  self.assertTrue(card['capabilities']['prompts'])
  self.assertGreaterEqual(len(card['prompts']),4)
  self.assertGreaterEqual(len(card['resources']),5)

  agents_html=self.client.get('/agents?lang=en').text
  self.assertIn('cursor://anysphere.cursor-deeplink/mcp/install',agents_html)
  self.assertIn('vscode:mcp/install?',agents_html)
  self.assertIn('claude mcp add --transport http quantum-aether',agents_html)

  mcp_meta=self.client.get('/.well-known/mcp.json').json
  self.assertEqual(mcp_meta['websiteUrl'],'https://ather-quantum.com/agents')
  self.assertEqual(mcp_meta['icons'][0]['src'],'https://ather-quantum.com/apple-touch-icon.png')
  self.assertEqual(mcp_meta['icons'][0]['mimeType'],'image/png')
  self.scanner.assert_not_called()



