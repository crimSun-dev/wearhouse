## Decisions

- **D1.** Accessory positions are resolved in the wardrobe, not by rewriting catalogue revisions, which are immutable. Catalogue browse keeps the coarse `accessory` facet. `accessory-subtypes@1` maps H&M product types:
  - Bag, Wallet → bag;
  - Hat/beanie, Cap/peaked, Hat/brim, Beanie, Cap, Felt hat, Bucket hat, Straw hat → headwear;
  - Sunglasses, Eyeglasses → eyewear;
  - Earring(s) → earrings;
  - Necklace → necklace;
  - Tie → tie;
  - Scarf → scarf;
  - Belt → belt;
  - Bracelet, Watch → wrist;
  - Ring → ring.

  Everything else stays `accessory`.
- **D2.** Revocation flags the owned item (`revoked_at`, `revoked_reason`) instead of deleting it. History, the export and the audit trail keep it. The unit stays `claimed`, so its key can never redeem again. Credentials of unclaimed units are revoked as before.
- **D3.** Moderation state lives on `look_share` (`moderation_state`, `moderated_by`, `moderated_at`, `moderation_reason`). Reports go in `share_report` (unique per reporter and share). Visibility checks treat `hidden` as invisible to non-owners.
- **D4.** An inspiration stores the projection JSON as it was when saved. It is the saver's private copy and grants nothing.
- **D5.** The completion/duplicate rerank is a heuristic stand-in for thesis Eq. 3, declared in the model info. The research RQ1 pipeline remains the evaluated implementation.
- **D6.** The measurements run against the local dev API and database: a laptop, not production. The evidence document says so.
