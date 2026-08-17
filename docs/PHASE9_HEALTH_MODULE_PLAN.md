# Phase 9 Health Module And Real Model Reliability

## Goal

Make MyAI distinguish between:

- configured model mode
- actual real-provider availability
- fallback-to-Stub product availability

Fallback keeps the product usable, but it does not prove the real model is working. Phase 9 turns real-model health into an explicit observable capability before Phase 8 smoke hardening continues.

## 9.1 Real Model Health Probe MVP

Purpose: let the user manually verify whether Chat, Task, Memory, and Embedding providers can call the real model.

Implemented baseline:

- Python Agent endpoint:
  - `POST /observability/model/probe`
- Probe checks:
  - chat LLM
  - task LLM
  - memory LLM
  - embedding model
- Probe does not expose secrets.
- Probe reports:
  - provider
  - model id
  - kind: real or stub
  - ok/status
  - latency
  - error type
  - safe error message
  - missing config fields
  - whether process proxy environment variables were detected
  - whether model SDK clients inherit proxy environment variables
- `GET /observability/summary` includes the latest probe result under `model.last_probe`.
- Java proxies the probe through:
  - `POST /observability/model/probe`
- Settings > System Health includes:
  - last real-model probe summary
  - a manual `实时探测真实模型` action

### Proxy Finding

During local validation, `HTTP_PROXY`, `HTTPS_PROXY`, and `ALL_PROXY` were set to `http://127.0.0.1:9`. Direct TCP connectivity to `ark.cn-beijing.volces.com:443` was healthy, but SDK calls failed because `httpx` inherited the broken proxy by default.

The model clients now default to `MYAI_MODEL_TRUST_ENV_PROXY=false`, so they use direct provider connectivity unless the user explicitly opts into environment proxy inheritance.

## 9.2 Error Classification

Initial categories:

- `authentication`
- `model_not_found`
- `rate_limit`
- `timeout`
- `network`
- `provider_5xx`
- `unknown`

Later improvements:

- Provider-specific parsing for Volcengine ARK response codes.
- Separate DNS/proxy/firewall classification where available.
- Cost/rate-limit hints in UI.

## 9.3 Runtime Reliability Metrics

Planned follow-up:

- Count real-provider attempts.
- Count real-provider successes.
- Count fallback events.
- Track rolling success rate.
- Track average latency.
- Track latest success and latest failure timestamps.

These counters should feed:

- observability summary
- system health center
- future Phase 8 smoke reports

## 9.4 Mode Policy

Recommended user-facing modes:

- `Stub only`: local/offline development.
- `Real with fallback`: default daily local use.
- `Real strict`: configuration validation and production readiness checks.

## Acceptance Criteria

- User can tell whether real model calls are currently working.
- User can tell whether MyAI is usable only because Stub fallback is active.
- Real-provider probe failures are actionable and do not expose secrets.
- Health center can trigger a live probe without making every settings-page refresh slow.

## Next Step

After 9.1, return to Phase 8.2 and include model health in smoke output:

- Stub-mode smoke must pass.
- Real-model probe may be optional but should report clear success/failure when enabled.
