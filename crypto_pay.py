# crypto_pay.py
# الدفع بالعملات المستقرة (USDT على Polygon وUSDC على Arbitrum) مع تحقق مباشر من الشبكة.
# لكل طلب مبلغ فريد (مثل 49.0137) حتى نعرف صاحب الدفعة، فعناوين المنصات (Binance/OKX) مشتركة وثابتة.
# المشتري يرسل رقم المعاملة (tx hash) فنقرأ إيصالها من الشبكة: لا نثق بأي معلومة من المتصفح.
import re
import secrets
from decimal import Decimal

import requests

TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
ADDRESS_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")
TX_RE = re.compile(r"^0x[0-9a-fA-F]{64}$")

NETWORKS = {
    "polygon-usdt": {
        "chain": "Polygon PoS", "chain_id": 137, "token": "USDT", "decimals": 6,
        "contract": "0xc2132d05d31c914a87c6611c10748aeb04b58e8f",
        "rpc": ["https://polygon-bor-rpc.publicnode.com", "https://polygon.drpc.org"],
        "confirmations": 30, "explorer": "https://polygonscan.com/tx/", "config": "USDT_POLYGON_ADDR",
    },
    "arbitrum-usdc": {
        "chain": "Arbitrum One", "chain_id": 42161, "token": "USDC", "decimals": 6,
        "contract": "0xaf88d065e77c8cc2239327c5edb3a432268e5831",  # USDC الأصلي (ليس USDC.e)
        "rpc": ["https://arbitrum-one-rpc.publicnode.com", "https://arb1.arbitrum.io/rpc"],
        "confirmations": 10, "explorer": "https://arbiscan.io/tx/", "config": "USDC_ARBITRUM_ADDR",
    },
}

# نقبل دفعة أُرسلت قبل إنشاء الطلب بخمس دقائق كحد أقصى (فرق الساعات بين الشبكة والخادم).
CLOCK_SKEW_SECONDS = 300


class ChainError(Exception):
    """تعذّر الوصول إلى الشبكة (كل نقاط RPC فشلت)."""


class ChainClient:
    def __init__(self, timeout=10, session=None):
        self.timeout = timeout
        self.http = session or requests.Session()

    def call(self, network, method, params):
        last = None
        for url in NETWORKS[network]["rpc"]:
            try:
                response = self.http.post(url, json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
                                          timeout=self.timeout)
                body = response.json()
                if "error" in body:
                    raise ChainError(str(body["error"])[:200])
                return body.get("result")
            except (requests.RequestException, ValueError, ChainError) as exc:
                last = exc
        raise ChainError(f"all RPC endpoints failed: {last}")


def enabled_networks(config):
    """الشبكات التي لها عنوان استلام صالح في الإعدادات."""
    return {key: dict(net, address=config[net["config"]].lower())
            for key, net in NETWORKS.items() if ADDRESS_RE.match(config.get(net["config"]) or "")}


def unique_amount(price, taken):
    """السعر + كسر عشوائي من 0.0001 إلى 0.0999، غير مستعمل في طلب مفتوح آخر."""
    base = Decimal(price)
    for _ in range(50):
        amount = base + Decimal(secrets.randbelow(999) + 1) / Decimal(10000)
        if str(amount) not in taken:
            return amount
    raise RuntimeError("no free unique amount")


def to_units(amount, decimals):
    return int(Decimal(amount) * (10 ** decimals))


def _topic_address(topic):
    return "0x" + topic[-40:].lower()


def verify_transfer(client, network, net, tx_hash, address, amount, not_before_ts):
    """يعيد (الحالة، تفاصيل). الحالات: OK, PENDING, CONFIRMING, FAILED, NO_TRANSFER, WRONG_AMOUNT, TOO_OLD."""
    receipt = client.call(network, "eth_getTransactionReceipt", [tx_hash])
    if not receipt:
        return "PENDING", {}
    if receipt.get("status") != "0x1":
        return "FAILED", {}
    received = 0
    for entry in receipt.get("logs", []):
        topics = entry.get("topics") or []
        if (entry.get("address", "").lower() == net["contract"] and len(topics) == 3
                and topics[0].lower() == TRANSFER_TOPIC and _topic_address(topics[2]) == address):
            received += int(entry.get("data") or "0x0", 16)
    if received == 0:
        return "NO_TRANSFER", {}
    expected = to_units(amount, net["decimals"])
    details = {"received": str(Decimal(received) / (10 ** net["decimals"]))}
    if received < expected:
        return "WRONG_AMOUNT", details
    block = int(receipt["blockNumber"], 16)
    latest = int(client.call(network, "eth_blockNumber", []), 16)
    confirmations = latest - block + 1
    details["confirmations"] = confirmations
    if confirmations < net["confirmations"]:
        return "CONFIRMING", details
    header = client.call(network, "eth_getBlockByNumber", [hex(block), False])
    if int(header["timestamp"], 16) < not_before_ts - CLOCK_SKEW_SECONDS:
        return "TOO_OLD", details  # معاملة أقدم من الطلب: ليست دفعته
    return "OK", details
