"""
Vercel serverless function: GET /api/order/<num>

Fetches a Shopify order and returns the parsed job card JSON payload.

Environment variables (set in Vercel dashboard):
  SHOPIFY_STORE  - myshopify handle, e.g. "the-design-lap"
  SHOPIFY_TOKEN  - Admin API access token (shpat_...)
  JOBCARD_SECRET - (optional) shared secret required in ?key= query for basic auth
"""
import json
import os
import re
import urllib.request
from http.server import BaseHTTPRequestHandler


STORE = os.environ.get("SHOPIFY_STORE", "")
TOKEN = os.environ.get("SHOPIFY_TOKEN", "")
SECRET = os.environ.get("JOBCARD_SECRET", "")  # optional

GRAPHQL_URL = f"https://{STORE}.myshopify.com/admin/api/2024-10/graphql.json"

ORDER_QUERY = """
query GetOrder($q: String!) {
  orders(first: 1, query: $q) {
    nodes {
      id
      name
      note
      tags
      customer { firstName lastName }
      lineItems(first: 50) {
        nodes {
          title
          quantity
          variantTitle
          sku
          customAttributes { key value }
        }
      }
    }
  }
}
"""


def shopify_query(query, variables):
    body = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request(
        GRAPHQL_URL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": TOKEN,
        },
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


BASE_MEDIA_ALIASES = {
    "standard": "Standard",
    "white": "Standard",
    "chrome": "Chrome",
    "hologram": "Hologram",
    "clear": "Clear",
}
LAMINATE_ALIASES = {
    "gloss": "Gloss",
    "high gloss": "Gloss",
    "matte": "Matte",
    "metallic": "Metallic",
    "sparkle": "Sparkle",
}
PLASTICS_BRAND_RE = re.compile(
    r"^(UFO|Acerbis|Polisport|Cycra|One Industries|Rekluse)\b", re.I
)


def parse_variant(variant_title):
    result = {"laminate": "", "base_media": ""}
    if not variant_title:
        return result
    for segment in [s.strip().lower() for s in variant_title.split("/")]:
        if segment in LAMINATE_ALIASES:
            result["laminate"] = LAMINATE_ALIASES[segment]
        elif segment in BASE_MEDIA_ALIASES:
            result["base_media"] = BASE_MEDIA_ALIASES[segment]
    return result


def parse_plastics_brand(title):
    if not title:
        return ""
    m = PLASTICS_BRAND_RE.search(title)
    return m.group(1).upper() if m else ""


def parse_bike_from_plastics_title(title):
    if not title:
        return ""
    m = re.search(r"\bfor\s+(.+)$", title)
    return m.group(1).strip() if m else ""


def parse_bike_from_attrs(attrs):
    year = (attrs.get("Year") or "").strip()
    make = (attrs.get("Make") or "").strip()
    model = (attrs.get("Model") or "").strip()
    return " ".join([p for p in (year, make, model) if p])


def parse_mini_plates_qty(value):
    if not value:
        return 0
    m = re.search(r"\((\d+)\s*@", value)
    if m:
        return int(m.group(1))
    if value.strip().lower().startswith("yes"):
        return 1
    return 0


def attrs_dict(custom_attributes):
    return {
        (a.get("key") or "").strip(): (a.get("value") or "").strip()
        for a in (custom_attributes or [])
    }


def value_yes(v):
    return bool(v) and str(v).strip().lower().startswith("yes")


DEFAULT_PATTERNS = {
    "CHK_INSTALL": {
        "any_key": ["Free Graphic Install", "Add-On: Plastics", "Add-On: Free Install"]
    },
    "CHK_MINI_PLATES": {"any_key": ["Add-On: Mini Plates"]},
    "CHK_CLEAR_SWINGARMS": {
        "any_key": [
            "Add-On: Clear Factory Swingarm",
            "Add-On: Clear Swingarm",
            "Add-On: Clear Swingarms",
        ],
        "line_item_sku": ["ADDON-CLEARSWING"],
    },
    "CHK_GUTS_SEAT": {
        "any_key": ["Add-On: GUTS Seat Cover", "Add-On: Seat Cover"],
        "line_item_title_contains": ["seat cover", "guts"],
    },
    "CHK_FORK_NEW_SHOWA": {"key_value": ["Add-On: Fork Decals", "New Showa"]},
    "CHK_FORK_SHOWA": {"key_value": ["Add-On: Fork Decals", "Showa"]},
    "CHK_FORK_WP": {"key_value": ["Add-On: Fork Decals", "WP"]},
    "CHK_FORK_KYB": {"key_value": ["Add-On: Fork Decals", "KYB"]},
    "CHK_FORK": {"key_value": ["Add-On: Fork Decals", "self"]},
}


def evaluate_checkbox(cb_name, main_attrs, line_items):
    rule = DEFAULT_PATTERNS.get(cb_name) or {}
    if "any_key" in rule:
        for key in rule["any_key"]:
            if value_yes(main_attrs.get(key)):
                return True
    if "key_value" in rule:
        key, needle = rule["key_value"]
        val = main_attrs.get(key, "")
        if val and needle.lower() in val.lower():
            if cb_name == "CHK_FORK_SHOWA" and val.lower().startswith("new showa"):
                return False
            return True
    if "line_item_sku" in rule:
        skus = [s.lower() for s in rule["line_item_sku"]]
        for li in line_items:
            if (li.get("sku") or "").lower() in skus:
                return True
    if "line_item_title_contains" in rule:
        needles = [n.lower() for n in rule["line_item_title_contains"]]
        for li in line_items:
            title = (li.get("title") or "").lower()
            if any(n in title for n in needles):
                return True
    return False


def build_job_card(order):
    line_items = order["lineItems"]["nodes"]
    main = None
    plastics_item = None
    for item in line_items:
        attrs = attrs_dict(item.get("customAttributes"))
        if "Model" in attrs and main is None:
            main = item
        title_low = (item.get("title") or "").lower()
        if "plastic kit" in title_low and " for " in title_low:
            plastics_item = item

    main_attrs = attrs_dict(main.get("customAttributes") if main else [])
    variant = parse_variant(main.get("variantTitle") if main else "")

    bike = parse_bike_from_attrs(main_attrs)
    if not bike and plastics_item:
        bike = parse_bike_from_plastics_title(plastics_item["title"])

    plastics_brand = ""
    if plastics_item:
        plastics_brand = parse_plastics_brand(plastics_item["title"])
    if not plastics_brand:
        plastics_brand = (main_attrs.get("Plastics Brand") or "").strip()

    mp_qty = parse_mini_plates_qty(main_attrs.get("Add-On: Mini Plates"))
    if mp_qty == 0:
        for li in line_items:
            if "mini plate" in (li.get("title") or "").lower():
                mp_qty = int(li.get("quantity") or 1)
                break

    # Prefer Rider Name from line item attrs (always readable + often differs from buyer).
    # Fall back to buyer's customer.firstName+lastName (requires read_customers scope).
    customer_name = (main_attrs.get("Rider Name") or "").strip()
    if not customer_name:
        customer = order.get("customer") or {}
        customer_name = f"{customer.get('firstName') or ''} {customer.get('lastName') or ''}".strip()

    designer_tag_fallback = ""
    for tag in order.get("tags", []) or []:
        t = tag.strip()
        if re.match(r"^#[A-Z]{2,3}$", t):
            designer_tag_fallback = t.lstrip("#")
            break

    checkboxes = {
        cb: evaluate_checkbox(cb, main_attrs, line_items)
        for cb in DEFAULT_PATTERNS.keys()
    }

    return {
        "shopify_num": order["name"].lstrip("#"),
        "customer_name": customer_name,
        "bike": bike,
        "notes": (order.get("note") or "").strip(),
        "base_media": variant["base_media"],
        "laminate": variant["laminate"],
        "plastics_brand": plastics_brand,
        "mini_plates_qty": mp_qty,
        "designer_tag_fallback": designer_tag_fallback,
        "checkboxes": checkboxes,
        # DEBUG: remove once customer_name is confirmed working
        "_debug_main_attrs_keys": sorted(main_attrs.keys()),
        "_debug_has_customer": bool(order.get("customer")),
    }


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Vercel routes /api/order/<num>?key=... here.
        # self.path looks like "/api/order/5161" or "/api/order/5161?key=xxx"
        path = self.path
        # Optional shared-secret check
        if SECRET:
            m = re.search(r"[?&]key=([^&]+)", path)
            provided = (m.group(1) if m else "")
            if provided != SECRET:
                self._send({"error": "unauthorized"}, status=401)
                return

        m = re.search(r"/api/order/(\d+)", path)
        if not m:
            self._send({"error": "bad path"}, status=400)
            return
        order_num = m.group(1)

        if not STORE or not TOKEN:
            self._send({
                "error": "Missing SHOPIFY_STORE or SHOPIFY_TOKEN environment variables in Vercel."
            }, status=500)
            return

        try:
            data = shopify_query(ORDER_QUERY, {"q": f"name:#{order_num}"})
            nodes = data.get("data", {}).get("orders", {}).get("nodes", [])
            if not nodes:
                self._send({"error": f"Order #{order_num} not found"})
                return
            self._send(build_job_card(nodes[0]))
        except Exception as e:
            self._send({"error": f"{type(e).__name__}: {e}"}, status=500)

    def _send(self, payload, status=200):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
