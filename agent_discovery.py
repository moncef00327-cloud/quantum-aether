"""Discoverable public TLS tools over a stateless MCP JSON-RPC endpoint."""
import base64
import datetime as dt
import json
import re
from urllib.parse import urlsplit
from flask import Response, current_app, jsonify, make_response, render_template, request
from werkzeug.exceptions import HTTPException
import badge_evidence
import quantum_vuln_scanner
import scan_experience

UPDATED='2026-11-08'
PROTOCOLS=('2025-11-25','2025-06-18')
VERSION='1.4.0'
DOMAIN_SCHEMA={'type':'object','properties':{'domain':{'type':'string','minLength':1,'maxLength':253,'description':'Public DNS hostname, for example example.com. HTTPS port 443 only.'}},'required':['domain'],'additionalProperties':False}
EMPTY_SCHEMA={'type':'object','properties':{},'additionalProperties':False}
ORDER_SCHEMA={'type':'object','properties':{'scan_id':{'type':'string','minLength':1,'description':'ID returned by scan_tls.'},'consent_immediate_delivery':{'type':'boolean','const':True,'description':'Set true only after the payer explicitly agrees to immediate delivery and the applicable withdrawal-right terms.'}},'required':['scan_id','consent_immediate_delivery'],'additionalProperties':False}
VERIFY_SCHEMA={'type':'object','properties':{'order_id':{'type':'string','minLength':1},'tx_hash':{'type':'string','pattern':'^0x[0-9a-fA-F]{64}$'}},'required':['order_id','tx_hash'],'additionalProperties':False}
REPORT_SCHEMA={'type':'object','properties':{'scan_id':{'type':'string','minLength':1,'description':'ID returned by scan_tls. A compatible x402 MCP client handles the Base USDC payment challenge.'}},'required':['scan_id'],'additionalProperties':False}
TOOLS=[
 {'name':'scan_tls','title':'Measure TLS and post-quantum key exchange','description':'Run a new, rate-limited TLS scan of a public hostname on port 443. Returns observation_status, measured time, negotiated group and certificate summary. Starts an external connection and stores a publicly accessible result. Does not judge application safety.', 'inputSchema':DOMAIN_SCHEMA,'annotations':{'readOnlyHint':False,'destructiveHint':False,'idempotentHint':False,'openWorldHint':True}},
 {'name':'get_tls_evidence','title':'Read stored TLS evidence without scanning','description':'Read existing TLS evidence with source, checked_at, expires_at and fresh/stale/undetermined/not_scanned state. Never starts a new network scan. A missing record is not proof that a domain is unsafe.', 'inputSchema':DOMAIN_SCHEMA,'annotations':{'readOnlyHint':True,'idempotentHint':True,'openWorldHint':False}},
 {'name':'get_methodology','title':'Understand measurement scope and limitations','description':'Get the documented measurement scope, observation states, certificate-grade rules and privacy limitations before interpreting a TLS result.','inputSchema':EMPTY_SCHEMA,'annotations':{'readOnlyHint':True,'idempotentHint':True,'openWorldHint':False}},
 {'name':'get_example_result','title':'Inspect an archived example without scanning','description':'Return an explicitly labeled archived example, not live telemetry. No payment and no network scan.','inputSchema':EMPTY_SCHEMA,'annotations':{'readOnlyHint':True,'idempotentHint':True,'openWorldHint':False}},
 {'name':'get_service_info','title':'Discover Quantum Aether capabilities and current pricing','description':'Get live endpoints, quotas, report price, x402 Base USDC checkout status and limitations.','inputSchema':EMPTY_SCHEMA,'annotations':{'readOnlyHint':True,'idempotentHint':True,'openWorldHint':False}},
 {'name':'get_full_report','title':'Purchase the full TLS report with x402','description':'Fetch the full report for a completed scan. If unpaid, returns a standard x402 v2 PaymentRequired challenge for exact USDC on Base. An x402-enabled MCP client may sign and retry under the buyer wallet’s own spend policy. Payment is settled before report access is returned.','inputSchema':REPORT_SCHEMA,'annotations':{'readOnlyHint':False,'destructiveHint':False,'idempotentHint':False,'openWorldHint':True}},
 {'name':'create_full_report_order','title':'Create a USDT Polygon payment order','description':'Create a one-time full-report order for an existing scan. This does not transfer funds. Only set consent_immediate_delivery true after the payer has expressly agreed to immediate delivery and applicable withdrawal terms. The payer must send USDT on Polygon and then submit its transaction hash using verify_full_report_payment.','inputSchema':ORDER_SCHEMA,'annotations':{'readOnlyHint':False,'destructiveHint':False,'idempotentHint':False,'openWorldHint':False}},
 {'name':'verify_full_report_payment','title':'Verify a Polygon transaction and unlock a paid report','description':'Submit the payer-provided Polygon transaction hash. The server checks the confirmed USDT transfer, exact order amount and recipient on chain. Returns the private report URL only after confirmation.','inputSchema':VERIFY_SCHEMA,'annotations':{'readOnlyHint':False,'destructiveHint':False,'idempotentHint':True,'openWorldHint':True}},
]


def methodology(base):
 return {'name':'Quantum Aether TLS observation methodology','version':VERSION,'updated':UPDATED,
  'description':'Measures one public HTTPS connection from the Quantum Aether server to a public IPv4 address, or IPv6 fallback, on port 443. Observes the negotiated TLS protocol and key-exchange group and performs a separate standard certificate handshake.',
  'key_exchange':{'hybrid_group':'X25519MLKEM768','evidence':'A completed observed ServerHello selection; a retry-only HelloRetryRequest is undetermined.'},
  'observation_states':{'observed_pq':'Hybrid post-quantum key exchange was observed.','observed_classical':'A classical key-exchange selection was observed.','undetermined':'The probe could not establish a completed selection; do not treat this as proof of classical-only support.'},
  'grades':{'A':'TLS 1.3 and observed hybrid key exchange, subject to certificate and protocol findings.','B':'TLS 1.3 without an observed hybrid exchange; read observation_status before concluding classical-only support.','C':'TLS 1.2 without a more severe finding.','F':'A severe certificate, legacy-protocol or weak-key finding.'},
  'limitations':scan_experience.LIMITATION,
  'not_provided':['application vulnerability assessment','permission to execute code or transmit secrets','numeric trust score','HSTS measurement','signed scan receipts'],
  'data_policy':{'stored_results':'Scan results are stored and can be publicly accessible. Do not submit confidential targets without accepting that policy.','indexing':'A noindex directive is not access control.'},
  'references':{'scan_policy':base+'/scanning','study':base+'/study/top-1000-post-quantum-tls','guide':base+'/guides/enable-x25519mlkem768-nginx','privacy':base+'/datenschutz?lang=en'}}


def manifest(base):
 cfg=current_app.config
 return {'schema_version':'1.0','manifest_type':'Quantum Aether service discovery; custom metadata, not an A2A Agent Card',
  'name':'Quantum Aether Observatory','description':'Check whether a public website negotiates hybrid post-quantum TLS key exchange; read timestamped observations, certificate summaries and explicit measurement limits.',
  'website':base+'/agents?lang=en','canonical_manifest':base+'/.well-known/agent-service.json','capabilities':['public_tls_scan','certificate_summary','post_quantum_key_exchange_observation','stored_evidence_lookup'],
  'keywords':['TLS','post-quantum','ML-KEM','X25519MLKEM768','HTTPS','certificate','cryptography'],
  'use_cases':['Measure the negotiated key exchange before applying a transport-security policy.','Re-check a public domain after changing TLS or CDN configuration.','Read existing evidence before deciding whether a fresh scan is needed.'],
  'endpoints':{'scan':{'url':base+'/api/scan','method':'POST','input':{'domain':'example.com'},'success_status':201},
   'quantum_scan':{'url':base+'/api/v1/quantum-scan','method':'POST'},'stored_evidence':{'url_template':base+'/api/v1/badge/{domain}','method':'GET','starts_scan':False},
   'methodology':{'url':base+'/api/v1/agent/methodology','method':'GET'},'example':{'url':base+'/api/v1/agent/example','method':'GET','is_live':False},'health':{'url':base+'/healthz','method':'GET'}},
  'mcp':{'url':base+'/mcp','transport':'streamable-http','mode':'stateless JSON responses; no SSE stream','protocol_versions':list(PROTOCOLS),'authentication':'none','tools':[t['name'] for t in TOOLS],'active_scan_tool':'scan_tls'},
  'pricing':{'scan_summary':{'amount':'0','currency':cfg['CURRENCY']},'full_report':{'amount':str(cfg['PRICE']),'currency':cfg['CURRENCY'],'purchase_method':'x402','network':'Base','token':'USDC','endpoint_template':base+'/api/v1/agent/report/{scan_id}','mcp_tool':'get_full_report','payment_authorization_required':True,'buyer_wallet_required':True,'purchase_documentation':base+'/openapi.yaml'},'x402':{'enabled':bool(re.fullmatch(r'0x[0-9a-fA-F]{40}',cfg.get('USDC_BASE_ADDR',''))),'status':'configured' if re.fullmatch(r'0x[0-9a-fA-F]{40}',cfg.get('USDC_BASE_ADDR','')) else 'disabled_missing_receiver','automatic_checkout':bool(re.fullmatch(r'0x[0-9a-fA-F]{40}',cfg.get('USDC_BASE_ADDR',''))),'buyer_wallet_required':True,'network':'eip155:8453','asset':'0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913','scheme':'exact','facilitator':'https://facilitator.payai.network'},'signed_receipts':{'enabled':False}},
  'limits':{'scan_attempts_per_client_per_hour':cfg['SCANS_PER_HOUR'],'global_scan_attempts_per_hour':cfg['GLOBAL_SCANS_PER_HOUR'],'rate_limit_status':429,'retry_after_seconds':3600},
  'documentation':{'human':base+'/agents?lang=en','openapi':base+'/openapi.yaml','llms':base+'/llms.txt','full_context':base+'/llms-full.txt','methodology':base+'/api/v1/agent/methodology','mcp_registry_metadata':base+'/api/v1/agent/mcp-server.json','source':'https://github.com/moncef00327-cloud/quantum-aether'},
  'directory_status':{'mcp_registry':'Official listing active; current MCP server version is '+VERSION+'.','x402_bazaar':'Not listed. The HTTP x402 endpoint and paid MCP tool are available when Base USDC receiving is configured.'},
  'privacy':methodology(base)['data_policy'],'terms':base+'/agb?lang=en','support':base+'/impressum?lang=en','limitations':scan_experience.LIMITATION}


def register(bp, services):
 base=services['base']
 def example():
  result=services['sample']()
  body=services['summary']('archived-example',result)
  body.update(is_example=True,is_live=False,scan_id=None,scan_url=base()+'/sample-report?lang=en',example_source='Published archived sample report; timestamp is historical, not request time.')
  return body

 def invoke_view(view, path, payload=None, headers=None, include_headers=False):
  with current_app.test_request_context(path,method='POST',json=payload or {},headers=headers or {}):
   response=current_app.make_response(view())
   body=response.get_json(silent=True) or {}
   return (response.status_code,body,dict(response.headers)) if include_headers else (response.status_code,body)

 @bp.get('/agents')
 def agents_page():
  return render_template('agents.html',agent_manifest=manifest(base()),agent_methodology=methodology(base()))

 @bp.get('/api/v1/agent/discovery')
 @bp.get('/.well-known/agent-service.json')
 def agent_service_manifest():
  response=jsonify(manifest(base()));response.headers['Cache-Control']='public, max-age=300'
  response.headers['Link']=f'<{base()}/.well-known/agent-service.json>; rel="canonical"'
  return response

 @bp.get('/api/v1/agent/methodology')
 def agent_methodology():
  return jsonify(methodology(base()))

 @bp.get('/api/v1/agent/example')
 def agent_example():
  return jsonify(example())

 @bp.get('/api/v1/agent/mcp-server.json')
 def agent_registry_metadata():
  # Honest remote registration metadata: this endpoint does not claim catalog acceptance.
  return jsonify({'$schema':'https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json',
   'name':'io.github.moncef00327-cloud/quantum-aether','title':'Quantum Aether','version':VERSION,
   'description':'Measure public TLS and post-quantum key exchange; read timestamped evidence and measurement limits.',
   'repository':{'url':'https://github.com/moncef00327-cloud/quantum-aether','source':'github','subfolder':'mcp'},
   'remotes':[{'type':'streamable-http','url':base()+'/mcp'}]})

 def rpc_error(code,message,request_id=None,status=400):
  return jsonify(jsonrpc='2.0',id=request_id,error={'code':code,'message':message}),status

 @bp.route('/mcp',methods=['GET','POST'],provide_automatic_options=False)
 def agent_mcp():
  origin=request.headers.get('Origin')
  if origin:
   expected=urlsplit(base())
   if origin.rstrip('/')!=f'{expected.scheme}://{expected.netloc}':
    return jsonify(error='origin_not_allowed'),403
  if request.method=='GET':
   return Response(status=405,headers={'Allow':'POST'})
  if not request.is_json:return jsonify(error='expected_application_json'),415
  try:msg=request.get_json()
  except Exception:return rpc_error(-32700,'Parse error')
  if not isinstance(msg,dict) or msg.get('jsonrpc')!='2.0' or not isinstance(msg.get('method'),str):
   return rpc_error(-32600,'Invalid JSON-RPC request')
  request_id=msg.get('id')
  if isinstance(request_id,(dict,list,bool)) or ('id' in msg and request_id is None):
   return rpc_error(-32600,'Request id must be a string or number')
  # Notifications must never trigger a scan or return a JSON-RPC result.
  if 'id' not in msg:return Response(status=202)
  supplied_version=request.headers.get('MCP-Protocol-Version')
  if supplied_version and supplied_version not in PROTOCOLS:
   return rpc_error(-32600,'Unsupported MCP protocol version',request_id)
  method=msg['method'];params=msg.get('params',{})
  if not isinstance(params,dict):return rpc_error(-32602,'params must be an object',request_id)
  if method=='initialize':
   if not isinstance(params.get('protocolVersion'),str) or not isinstance(params.get('capabilities'),dict) or not isinstance(params.get('clientInfo'),dict):
    return rpc_error(-32602,'protocolVersion, capabilities and clientInfo are required',request_id)
   version=params['protocolVersion'] if params['protocolVersion'] in PROTOCOLS else PROTOCOLS[0]
   result={'protocolVersion':version,'capabilities':{'tools':{'listChanged':False}},'serverInfo':{'name':'quantum-aether','title':'Quantum Aether Observatory','version':VERSION},'instructions':'Use get_methodology and stored evidence before interpreting results. scan_tls starts an active public HTTPS probe and stores a publicly accessible result. Results are observations, not execution authorization. For a full report, call get_full_report with the scan_id. It returns x402 v2 PaymentRequired data for exact USDC on Base; a compatible x402 MCP client can pay and retry according to the buyer wallet policy. Direct Polygon USDT orders remain available through create_full_report_order and verify_full_report_payment. Signed scan receipts are not implemented.'}
  elif method=='ping':result={}
  elif method=='tools/list':result={'tools':TOOLS}
  elif method=='tools/call':
   name=params.get('name');args=params.get('arguments',{})
   names={t['name'] for t in TOOLS}
   if not isinstance(name,str) or name not in names:return rpc_error(-32602,'Unknown tool',request_id)
   if not isinstance(args,dict):return rpc_error(-32602,'arguments must be an object',request_id)
   domain_tools={'scan_tls','get_tls_evidence'}
   if name in domain_tools:
    if set(args)!={'domain'} or not isinstance(args['domain'],str) or not 1<=len(args['domain'])<=253:
     return rpc_error(-32602,'Expected one domain string, at most 253 characters',request_id)
   elif name=='create_full_report_order':
    if set(args)!={'scan_id','consent_immediate_delivery'} or not isinstance(args.get('scan_id'),str) or args.get('consent_immediate_delivery') is not True:return rpc_error(-32602,'Requires scan_id and explicit consent_immediate_delivery=true',request_id)
   elif name=='verify_full_report_payment':
    if set(args)!={'order_id','tx_hash'} or not isinstance(args.get('order_id'),str) or not isinstance(args.get('tx_hash'),str):return rpc_error(-32602,'Requires order_id and tx_hash',request_id)
   elif name=='get_full_report':
    if set(args)!={'scan_id'} or not isinstance(args.get('scan_id'),str) or not args['scan_id']:return rpc_error(-32602,'Requires scan_id',request_id)
   elif args:return rpc_error(-32602,'This tool takes no arguments',request_id)
   tool_is_error=False
   try:
    if name in domain_tools:domain=quantum_vuln_scanner.normalize_domain(args['domain'])
    if name=='scan_tls':
     scan_id,raw=services['scan'](domain,'mcp');value=services['summary'](scan_id,raw)
    elif name=='get_tls_evidence':value=dict(badge_evidence.for_domain(services['db'](),domain),verification_url=base()+'/verify/'+domain)
    elif name=='get_methodology':value=methodology(base())
    elif name=='get_example_result':value=example()
    elif name=='get_full_report':
     payment_meta=params.get('_meta',{})
     payment=payment_meta.get('x402/payment') if isinstance(payment_meta,dict) else None
     headers={}
     if payment is not None:
      if not isinstance(payment,dict):return rpc_error(-32602,'x402/payment must be an object',request_id)
      encoded=base64.urlsafe_b64encode(json.dumps(payment,separators=(',',':')).encode()).decode().rstrip('=')
      headers['PAYMENT-SIGNATURE']=encoded
     status,value,response_headers=invoke_view(lambda:services['x402_report'](args['scan_id']),f"/api/v1/agent/report/{args['scan_id']}",headers=headers,include_headers=True)
     if status==402:
      challenge=json.loads(base64.b64decode(response_headers['PAYMENT-REQUIRED']))
      value=challenge
      result={'content':[{'type':'text','text':json.dumps(value,separators=(',',':'))}],'structuredContent':value,'isError':True}
     elif status>=400 or status==202:
      value={'http_status':status,**value}
      result={'content':[{'type':'text','text':json.dumps(value,ensure_ascii=False)}],'structuredContent':value,'isError':True}
     else:
      response_meta={}
      settlement_header=response_headers.get('PAYMENT-RESPONSE')
      if settlement_header:response_meta['x402/payment-response']=json.loads(base64.b64decode(settlement_header))
      result={'content':[{'type':'text','text':json.dumps(value,ensure_ascii=False)}],'structuredContent':value,'isError':False,**({'_meta':response_meta} if response_meta else {})}
    elif name=='create_full_report_order':
     status,value=invoke_view(services['crypto_create_order'],'/api/v1/crypto/orders',{'scan_id':args['scan_id'],'network':'polygon-usdt','consent_immediate_delivery':True})
     if status>=400:value={'http_status':status,**value};tool_is_error=True
    elif name=='verify_full_report_payment':
     status,value=invoke_view(services['crypto_verify'],f"/api/v1/crypto/orders/{args['order_id']}/verify",{'tx_hash':args['tx_hash']})
     if status>=400 or status==202:value={'http_status':status,**value};tool_is_error=status>=400
    else:value=manifest(base())
    if name!='get_full_report':result={'content':[{'type':'text','text':json.dumps(value,ensure_ascii=False)}],'structuredContent':value,'isError':tool_is_error}
   except quantum_vuln_scanner.ScanError as exc:
    value={'error':exc.code,'message':str(exc)}
    result={'content':[{'type':'text','text':json.dumps(value)}],'structuredContent':value,'isError':True}
   except HTTPException as exc:
    value={'error':'rate_limited' if exc.code==429 else 'request_failed','http_status':exc.code}
    if exc.code==429:value['retry_after_seconds']=3600
    result={'content':[{'type':'text','text':json.dumps(value)}],'structuredContent':value,'isError':True}
   except Exception:
    current_app.logger.exception('Remote MCP tool failed')
    return rpc_error(-32603,'Internal tool error',request_id,500)
  else:return rpc_error(-32601,'Method not found',request_id,404)
  response=jsonify(jsonrpc='2.0',id=request_id,result=result)
  response.headers['Cache-Control']='no-store'
  return response
