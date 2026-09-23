# Architecture and safety boundary

## Components

- **WiHotspot/create_ap:** provisions the access point and currently provides
  DHCP, DNS, NAT and hostapd orchestration.
- **openNDS:** enforces pre-authentication and grants a client a session after
  the FAS approves it.
- **FAS/payment service:** serves the HTTPS portal, creates payment attempts,
  verifies provider callbacks, and requests an openNDS authorization.
- **Database:** stores plans, payment attempts, idempotency keys, client
  bindings, grants and audit events.

## Non-negotiable rules

1. A browser redirect is not proof of payment. Only a verified provider
   webhook may create a grant.
2. The FAS uses HTTPS and a high-entropy, separately stored openNDS `faskey`.
3. Provider and portal domains are explicitly reachable from the pre-auth
   walled garden.
4. No arbitrary HTTPS interception is attempted.
5. One component must own the effective firewall policy. `create_ap` and
   openNDS must not be enabled together until packet-path tests prove that an
   unpaid client cannot forward traffic.
6. Credentials, webhook secrets, database URLs and FAS keys remain in `.env`
   or an OS secret store and are never committed.

## Provider-neutral payment contract

The portal will expose an internal adapter with these operations:

- `create_payment(plan_id, client_id, idempotency_key)`
- `verify_webhook(headers, body)`
- `get_payment_status(provider_reference)`
- `grant_entitlement(payment_id)`

Provider-specific code stays behind that boundary, allowing M-Pesa/Daraja,
Stripe or another provider to be selected without changing the openNDS layer.

## Open questions before live payment

- Payment provider and currency.
- Single laptop versus multiple gateways.
- Time, data, speed, or combined plans.
- Public HTTPS hostname and FAS hosting location.
