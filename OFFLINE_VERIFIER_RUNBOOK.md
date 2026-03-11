# DIIaC Offline Verifier Runbook

This runbook describes a minimal offline verification workflow for a governed execution decision pack.

## Inputs
- `execution_id`
- Signed pack export generated from: `GET /decision-pack/<execution_id>/export-signed`
- Runtime public keys from: `GET /verify/public-keys`

## Workflow
1. Export signed decision pack:
   - call `GET /decision-pack/<execution_id>/export-signed`
   - capture `zip_path`, `sig_path`, and `sigmeta_path`
2. Gather verification references:
   - call `GET /verify/execution/<execution_id>`
   - record `pack_hash`, `manifest_hash`, `merkle_root`
3. Verify runtime key registry:
   - call `GET /verify/public-keys`
   - confirm expected `signing_key_id` exists
4. Verify pack consistency:
   - call `POST /verify/pack` with:
     - `execution_id`
     - `pack_hash`
     - `manifest_hash`
   - expect `overall_valid=true`
5. Verify merkle proof for artifacts:
   - call `GET /executions/<execution_id>/merkle/proof/<artefact_name>`
   - pass response directly into `POST /verify/merkle-proof`
   - expect `proof_valid=true`

## Sample commands
```bash
# 1) Export signed pack
curl -s "http://localhost:8000/decision-pack/${EXECUTION_ID}/export-signed" | jq

# 2) Verify execution state
curl -s "http://localhost:8000/verify/execution/${EXECUTION_ID}" | jq

# 3) Verify public keys
curl -s "http://localhost:8000/verify/public-keys" | jq

# 4) Verify pack integrity
curl -s -X POST "http://localhost:8000/verify/pack" \
  -H 'Content-Type: application/json' \
  -d "{\"execution_id\":\"${EXECUTION_ID}\",\"pack_hash\":\"${PACK_HASH}\",\"manifest_hash\":\"${MANIFEST_HASH}\"}" | jq

# 5) Verify merkle proof for board_report.json
PROOF_JSON=$(curl -s "http://localhost:8000/executions/${EXECUTION_ID}/merkle/proof/board_report.json")
curl -s -X POST "http://localhost:8000/verify/merkle-proof" \
  -H 'Content-Type: application/json' \
  -d "$PROOF_JSON" | jq
```

## Tamper-check expectations
- Wrong `pack_hash` or wrong `manifest_hash` in `/verify/pack` should produce `overall_valid=false`.
- Modified merkle siblings/index/root in `/verify/merkle-proof` should produce `proof_valid=false`.
