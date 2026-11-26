"""Write the synthetic Wearhouse demo catalogue CSV (and its .sha256) used by the public staging demo.

Every row is INVENTED for the demo: no row is copied from H&M's articles.csv (which may not be redistributed), and
every description says so. The columns follow the `hm-articles@1` mapping so the ordinary
`wearhouse import-catalogue` pipeline (facts, slot rule, publication) handles them like any other source.

Article ids continue the original 26 staging records (900000-900025), so re-running the import is idempotent and
never touches those. Output is deterministic: the same script always writes the same bytes and checksum.

    python tools/make_demo_catalogue.py            # writes apps/api/fixtures/demo-catalogue/wearhouse-demo-catalogue.csv
"""
from __future__ import annotations

import csv
import hashlib
import io
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "apps" / "api" / "fixtures" / "demo-catalogue" / "wearhouse-demo-catalogue.csv"
FIRST_ID = 900026
NOTE = "Synthetic demo record. Not an H&M article."

UPPER, LOWER, FULL, SHOES, ACC = ("Garment Upper body", "Garment Lower body", "Garment Full body", "Shoes",
                                  "Accessories")

# (name, product_type_name, product_group_name, colours, one-line description)
STYLES: list[tuple[str, str, str, tuple[str, ...], str]] = [
    # ---- tops
    ("Basic crew-neck tee", "T-shirt", UPPER, ("White", "Black", "Grey", "Light Beige"), "Soft cotton jersey with a classic fit."),
    ("Oversized graphic tee", "T-shirt", UPPER, ("Off White", "Black"), "Boxy cut with a printed chest graphic."),
    ("Pocket tee", "T-shirt", UPPER, ("Khaki green", "Dark Blue"), "Heavyweight cotton with a chest pocket."),
    ("Long-sleeve waffle top", "Top", UPPER, ("Light Beige", "Dark Grey"), "Textured waffle knit for cooler evenings."),
    ("Linen camp-collar shirt", "Shirt", UPPER, ("Light Blue", "Beige", "Off White"), "Breathable linen with a relaxed camp collar."),
    ("Short-sleeve batik-print shirt", "Shirt", UPPER, ("Dark Blue", "Dark Red"), "Lightweight viscose with an all-over print."),
    ("Poplin office shirt", "Shirt", UPPER, ("White", "Light Blue", "Light Pink"), "Crisp cotton poplin, regular fit."),
    ("Flannel check shirt", "Shirt", UPPER, ("Dark Red", "Dark Green"), "Brushed cotton flannel in a check."),
    ("Puff-sleeve blouse", "Blouse", UPPER, ("White", "Light Pink", "Light Yellow"), "Airy cotton with gathered sleeves."),
    ("Satin button blouse", "Blouse", UPPER, ("Off White", "Dark Green"), "Fluid satin with covered buttons."),
    ("Ribbed polo", "Polo shirt", UPPER, ("Navy", "Off White"), "Fine rib knit polo with a short placket."),
    ("Pique polo", "Polo shirt", UPPER, ("White", "Dark Green", "Light Blue"), "Classic cotton pique."),
    ("Cropped tank", "Vest top", UPPER, ("White", "Light Pink"), "Stretch rib, cropped length."),
    ("Linen-blend vest top", "Vest top", UPPER, ("Beige", "Black"), "Loose linen-blend tank."),
    ("Crew-neck sweatshirt", "Sweater", UPPER, ("Grey", "Dark Blue", "Light Green"), "Brushed-back cotton fleece."),
    ("Fine-knit sweater", "Sweater", UPPER, ("Light Beige", "Black"), "Lightweight cotton-blend knit."),
    ("Pullover hoodie", "Hoodie", UPPER, ("Black", "Light Purple"), "Cotton-blend hoodie with a kangaroo pocket."),
    ("V-neck cardigan", "Cardigan", UPPER, ("Off White", "Dark Blue"), "Soft knit with a button front."),
    ("Cropped cardigan", "Cardigan", UPPER, ("Light Pink", "Light Green"), "Short boxy knit cardigan."),
    ("Sports tee", "T-shirt", UPPER, ("Black", "Turquoise"), "Quick-dry training tee."),
    # ---- outerwear (slot rule: upper-body Jacket/Coat/Blazer/Outdoor Waistcoat -> outer)
    ("Packable windbreaker", "Jacket", UPPER, ("Yellow", "Navy"), "Water-repellent shell that folds into its pocket."),
    ("Hooded rain jacket", "Jacket", UPPER, ("Black", "Dark Green", "Orange"), "Taped seams and an adjustable hood."),
    ("Bomber jacket", "Jacket", UPPER, ("Black", "Khaki green"), "Lightweight bomber with rib trims."),
    ("Utility overshirt jacket", "Jacket", UPPER, ("Beige", "Dark Brown"), "Twill jacket with four patch pockets."),
    ("Corduroy jacket", "Jacket", UPPER, ("Dark Beige", "Dark Brown"), "Cotton corduroy, boxy fit."),
    ("Unstructured blazer", "Blazer", UPPER, ("Dark Blue", "Beige", "Black"), "Soft-shouldered linen-blend blazer."),
    ("Double-breasted blazer", "Blazer", UPPER, ("Grey", "Off White"), "Tailored fit with peak lapels."),
    ("Wool-blend coat", "Coat", UPPER, ("Dark Grey", "Light Beige"), "Single-breasted coat for travel to cool climates."),
    ("Padded gilet", "Outdoor Waistcoat", UPPER, ("Navy", "Beige"), "Light padding and a stand collar."),
    # ---- bottoms
    ("Straight-leg jeans", "Trousers", LOWER, ("Blue", "Light Blue", "Black"), "Rigid cotton denim, straight leg."),
    ("Wide-leg jeans", "Trousers", LOWER, ("Light Blue", "Dark Blue"), "High waist and a full wide leg."),
    ("Slim chinos", "Trousers", LOWER, ("Navy", "Beige", "Dark Green"), "Stretch cotton twill, slim fit."),
    ("Linen drawstring trousers", "Trousers", LOWER, ("Off White", "Khaki green"), "Breathable linen with an elastic waist."),
    ("Tailored trousers", "Trousers", LOWER, ("Black", "Grey"), "Pressed crease, regular fit."),
    ("Cargo trousers", "Trousers", LOWER, ("Khaki green", "Black"), "Cotton ripstop with bellow pockets."),
    ("Jogger sweatpants", "Trousers", LOWER, ("Grey", "Black"), "Cuffed fleece joggers."),
    ("Denim shorts", "Shorts", LOWER, ("Light Blue", "White"), "Mid-rise denim shorts."),
    ("Chino shorts", "Shorts", LOWER, ("Beige", "Navy"), "Cotton twill, above-the-knee."),
    ("Running shorts", "Shorts", LOWER, ("Black", "Dark Blue"), "Lightweight shorts with an inner brief."),
    ("A-line denim skirt", "Skirt", LOWER, ("Blue", "Black"), "Mid-length denim skirt."),
    ("Satin midi skirt", "Skirt", LOWER, ("Light Beige", "Dark Green"), "Bias-cut satin midi skirt."),
    ("Tiered maxi skirt", "Skirt", LOWER, ("White", "Dark Red"), "Light cotton in soft tiers."),
    ("Leggings", "Leggings/Tights", LOWER, ("Black", "Dark Grey"), "High-waisted stretch leggings."),
    # ---- full body
    ("Linen shirt dress", "Dress", FULL, ("Light Blue", "Beige"), "Belted linen shirt dress."),
    ("Floral sundress", "Dress", FULL, ("Light Yellow", "Light Pink"), "Thin straps and a floral print."),
    ("Knit midi dress", "Dress", FULL, ("Black", "Light Beige"), "Fine rib knit, close fit."),
    ("T-shirt dress", "Dress", FULL, ("Grey", "Navy"), "Relaxed jersey dress."),
    ("Kebaya-inspired dress", "Dress", FULL, ("Off White", "Dark Purple"), "Fitted bodice with a lace-look trim."),
    ("Utility jumpsuit", "Jumpsuit/Playsuit", FULL, ("Khaki green", "Black"), "Cotton jumpsuit with a belt."),
    ("Linen playsuit", "Jumpsuit/Playsuit", FULL, ("Beige", "Light Blue"), "Short linen playsuit."),
    # ---- footwear
    ("Leather sneakers", "Sneakers", SHOES, ("White", "Black"), "Minimal low-top leather sneakers."),
    ("Running shoes", "Sneakers", SHOES, ("Grey", "Black"), "Cushioned mesh running shoes."),
    ("Slip-on canvas shoes", "Sneakers", SHOES, ("Navy", "Off White"), "Elasticated canvas slip-ons."),
    ("Rubber slides", "Sandals", SHOES, ("Black", "Beige"), "Moulded slides for wet days."),
    ("Strappy sandals", "Sandals", SHOES, ("Dark Brown", "Black"), "Leather-look straps and a flat sole."),
    ("Chelsea boots", "Boots", SHOES, ("Black", "Dark Brown"), "Elastic side panels and a pull tab."),
    ("Derby shoes", "Other shoe", SHOES, ("Black", "Dark Brown"), "Lace-up leather derbies."),
    ("Ballet flats", "Ballerinas", SHOES, ("Black", "Beige"), "Soft round-toe flats."),
    ("Block-heel pumps", "Pumps", SHOES, ("Black", "Light Beige"), "Mid block heel, pointed toe."),
    # ---- accessories (accessory-subtypes@1 positions)
    ("Canvas tote bag", "Bag", ACC, ("Off White", "Black"), "Roomy canvas tote."),
    ("Mini shoulder bag", "Bag", ACC, ("Dark Brown", "Light Pink"), "Small shoulder bag with a zip top."),
    ("Nylon backpack", "Bag", ACC, ("Black", "Dark Green"), "Water-repellent daypack."),
    ("Bucket hat", "Hat/brim", ACC, ("Beige", "Black"), "Cotton twill bucket hat."),
    ("Baseball cap", "Cap/peaked", ACC, ("Navy", "White"), "Adjustable six-panel cap."),
    ("Straw hat", "Hat/brim", ACC, ("Light Beige",), "Wide-brim woven hat."),
    ("Square sunglasses", "Sunglasses", ACC, ("Black", "Dark Brown"), "UV400 square frames."),
    ("Round sunglasses", "Sunglasses", ACC, ("Gold",), "Thin metal round frames."),
    ("Woven leather belt", "Belt", ACC, ("Dark Brown", "Black"), "Braided belt with a metal buckle."),
    ("Printed bandana scarf", "Scarf", ACC, ("Dark Red", "Navy"), "Cotton square scarf."),
    ("Silk tie", "Tie", ACC, ("Dark Blue", "Dark Red"), "Classic-width silk tie."),
    ("Chain necklace", "Necklace", ACC, ("Gold", "Silver"), "Fine curb-chain necklace."),
    ("Hoop earrings", "Earring", ACC, ("Gold", "Silver"), "Small polished hoops."),
    ("Analogue watch", "Watch", ACC, ("Silver", "Black"), "Minimal dial on a mesh strap."),
    ("Beaded bracelet", "Bracelet", ACC, ("Light Beige", "Turquoise"), "Stretch bracelet with glass beads."),
    ("Signet ring", "Ring", ACC, ("Gold", "Silver"), "Smooth flat-top ring."),
    ("Compact umbrella", "Umbrella", ACC, ("Black", "Navy"), "Folding umbrella for sudden showers."),
]

COLUMNS = ("article_id", "prod_name", "product_type_name", "product_group_name", "colour_group_name", "detail_desc")


def rows() -> list[dict[str, str]]:
    out, n = [], FIRST_ID
    for name, ptype, group, colours, desc in STYLES:
        for colour in colours:
            out.append({"article_id": str(n), "prod_name": name, "product_type_name": ptype,
                        "product_group_name": group, "colour_group_name": colour,
                        "detail_desc": f"{desc} {NOTE}"})
            n += 1
    return out


def render() -> bytes:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=COLUMNS, lineterminator="\n")
    w.writeheader()
    w.writerows(rows())
    return buf.getvalue().encode("utf-8")


def main() -> int:
    data = render()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(data)
    digest = hashlib.sha256(data).hexdigest()
    OUT.with_name(OUT.name + ".sha256").write_text(f"{digest}  {OUT.name}\n", encoding="utf-8")
    print(f"{len(rows())} rows -> {OUT} ({digest})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
