import sys, json, concurrent.futures as cf
sys.path.insert(0, "/var/www/quantum_saas")
import quantum_vuln_scanner as q
domains = [d.strip() for d in open(sys.argv[1]) if d.strip()]
out = open(sys.argv[2], "w")
def one(rank_d):
    rank, d = rank_d
    try:
        r = q.scan(d)
        r.pop("ip", None)
        return {"rank": rank, "domain": d, "ok": True, **r}
    except Exception as e:
        return {"rank": rank, "domain": d, "ok": False, "error": f"{type(e).__name__}: {e}"[:200]}
with cf.ThreadPoolExecutor(24) as ex:
    for i, res in enumerate(ex.map(one, enumerate(domains, 1)), 1):
        out.write(json.dumps(res, default=str) + "\n"); out.flush()
        if i % 100 == 0: print(i, flush=True)
