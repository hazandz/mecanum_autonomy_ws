# WP05 `warehouse_map2` static approval metadata activation

## Classification and exact base

- Classification: `L1_MAP_METADATA_APPROVAL_AND_DECLARED_UNVERIFIED_ACTIVATION`.
- Exact integration/source base: `a8eed8712ad7e20ae4d9e7665a4d07dacbde9047`.
- Architecture SHA-256: `432eeac363a595cfcf7e81c4b66054fb674dba140a2ef3cffecd617ab8136204`.
- Before independent audit and integration, this is a review candidate only.

## Exact subject and evidence references

This candidate changes only approval and world-frame metadata references for the existing map subject. Identity/content remain `map_id: warehouse_map2`, `artifact_identity: 4a8a23d0-7e27-4a50-8201-dd1abf1a3db4`, and `map_content_hash: 2bd9ff0a40eaeb61c2359aab4bb213da623ab56746debe591edd4a54c2229f90`. `map.yaml` SHA-256 is `5073762401784f67e856b5018656ad869ecc26e723f85e5979054eadc7876a68`; `map.pgm` SHA-256 is `32f8a3eb626ebddecc15843748de0db8c6f7adc1b45a5edc1b1b1886407aef55`.

The approval reference is `https://github.com/hazandz/mecanum_autonomy_ws.git@a8eed8712ad7e20ae4d9e7665a4d07dacbde9047:docs/governance/evidence/WP-05_WAREHOUSE_MAP2_SIM_EVAL_STATIC_APPROVAL.json`, SHA-256 `25f16fb3f7e1a668b73fc3d1e14ba51d851a55a2046a1560c44cf5f5aaaa5f7d`. The world declaration reference is `https://github.com/hazandz/mecanum_autonomy_ws.git@410d9cb70518b64d3c76c2ef99b11b69d1da6701:docs/governance/evidence/WP-05_WAREHOUSE_MAP2_WORLD_FRAME_DECLARATION.json`, SHA-256 `4002e9cd93363f488eb92149d51ca60598922ac11bf252720b8b01a245407294`. Both records identify the same map identity/content hash.

## Post-integration disposition and limits

Only after independent audit PASS for this exact candidate, separate User authorization, fast-forward integration, and remote-ref verification, metadata will state `approval_status: approved` solely for `SIM_EVAL_NAV2_BASELINE_STATIC_MAP_ARTIFACT_SELECTION`. The artifact is eligible as a static profile input for Step 5, not a resolved profile. Its world-frame state is only `DECLARED_UNVERIFIED`.

No map/world equivalence, transform, metric alignment, Map Server load, AMCL, TF, runtime-compatibility, or runtime-authority claim is made. The map is not navigation-ready. A future Map Server may bind only to `artifacts/maps/warehouse_map2/map.yaml`.

Older documents describing this map as `draft` or `NOT_DECLARED` are historical source-base snapshots. This candidate supersedes them only for current metadata after its integration conditions; it does not edit those historical records. Runtime compatibility remains `NOT_VALIDATED`. No `ResolvedConfigV3`, `config_hash`, runtime evidence, runtime authorization, or WP-05 closure is created. WP-04/WP-05 and Gate A/Gate B statuses are unchanged.
