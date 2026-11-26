"""Finish the synthetic demo catalogue after `wearhouse import-catalogue --publish`, `generate-media` and
`assign-sizes`: sandbox offers for products without one (never overwrites staff prices) and the 12-piece
'starter-kit' collection. Prints the kit's product ids for WEARHOUSE_STARTER_KIT. Idempotent.

Run with the same WEARHOUSE_* environment as the wearhouse CLI, as an existing admin/catalogue_editor account:

    python tools/finish_demo_catalogue.py --operator-issuer ISS --operator-subject SUB
"""
from __future__ import annotations

import argparse
import json
import sys
import uuid

# category -> (sandbox price IDR, stock per size / per one-size product). Mock values, labelled sandbox.
PRICES = {
    "T-shirt": (149000, 40), "Top": (179000, 30), "Shirt": (299000, 24), "Blouse": (279000, 24),
    "Polo shirt": (229000, 24), "Vest top": (129000, 30), "Sweater": (349000, 20), "Hoodie": (379000, 20),
    "Cardigan": (399000, 18), "Jacket": (549000, 16), "Blazer": (699000, 12), "Coat": (899000, 10),
    "Outdoor Waistcoat": (449000, 15), "Trousers": (349000, 22), "Shorts": (199000, 25), "Skirt": (299000, 20),
    "Leggings/Tights": (169000, 30), "Dress": (499000, 14), "Jumpsuit/Playsuit": (459000, 12),
    "Sneakers": (529000, 18), "Sandals": (199000, 24), "Boots": (649000, 12), "Other shoe": (599000, 12),
    "Ballerinas": (349000, 14), "Pumps": (499000, 12), "Shoes": (599000, 12), "Bag": (289000, 30),
    "Hat/brim": (149000, 30), "Hat/beanie": (119000, 30),
    "Cap/peaked": (129000, 40), "Sunglasses": (199000, 30), "Belt": (179000, 30), "Scarf": (159000, 24),
    "Tie": (199000, 20), "Necklace": (149000, 30), "Earring": (99000, 40), "Watch": (749000, 10),
    "Bracelet": (89000, 40), "Ring": (99000, 30), "Umbrella": (119000, 40),
}

# The starter wardrobe: a mix-and-match tropical everyday set, by synthetic article id (the original four first).
STARTER_KIT = (
    "900000",  # Relaxed linen shirt, White
    "900010",  # Striped cotton tee, Navy
    "900026",  # Basic crew-neck tee, White
    "900013",  # Relaxed chinos, Khaki
    "900093",  # Straight-leg jeans, Blue
    "900014",  # Linen shorts, Beige
    "900011",  # Light rain parka, Khaki
    "900019",  # Canvas sneakers, White
    "900143",  # Rubber slides, Black
    "900025",  # Crossbody bag, Black
    "900161",  # Bucket hat, Beige
    "900022",  # Leather belt, Brown
)
NAMESPACE = "wearhouse-synthetic-demo"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--operator-issuer", required=True)
    p.add_argument("--operator-subject", required=True)
    a = p.parse_args(argv)

    from sqlalchemy import text

    from wearhouse.bootstrap.cli import _runtime
    from wearhouse.bootstrap.container import build_services
    from wearhouse.identity.ports import InvalidToken

    settings, engine, _ = _runtime()

    class _NoTokens:
        def verify(self, token):
            raise InvalidToken("cli")

    services = build_services(settings, engine, _NoTokens())
    principal = services.identity.operator_principal(issuer=a.operator_issuer, subject=a.operator_subject)

    rules = [{"category": c, "price_idr": price, "stock": stock} for c, (price, stock) in PRICES.items()]
    offers = services.commerce_staff.bulk_offers(principal, rules=rules, overwrite=False)
    written = sum(r["written"] for r in offers["results"])

    with engine.connect() as conn:
        ids = dict(conn.execute(text(
            "SELECT p.external_id, p.id FROM product p JOIN catalogue_source s ON s.id = p.source_id"
            " WHERE s.namespace = :ns AND p.external_id = ANY(:ext) AND p.publication_state = 'published'"),
            {"ns": NAMESPACE, "ext": list(STARTER_KIT)}).all())
    missing = [e for e in STARTER_KIT if e not in ids]
    if missing:
        print(f"refusing: starter-kit articles not published yet: {', '.join(missing)}", file=sys.stderr)
        return 2
    kit = [uuid.UUID(str(ids[e])) for e in STARTER_KIT]
    services.publication.put_collection(principal, "starter-kit", "Every new wardrobe starts with these", kit)
    print(json.dumps({"offers_written": written, "starter_kit": [str(k) for k in kit],
                      "WEARHOUSE_STARTER_KIT": ",".join(str(k) for k in kit)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
