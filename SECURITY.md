# Security policy

## Supported versions

| Version | Supported |
| :--- | :--- |
| 1.x | Yes |

## Reporting a vulnerability

Please **do not open a public issue** for security problems. Use GitHub's
[private security advisory](https://github.com/redhunt07/ha-solar-of-things-cloud/security/advisories/new)
flow instead.

Include, when possible:

- the integration version and Home Assistant version;
- what you expected and what happened;
- a minimal reproduction;
- logs with **tokens removed** (the integration never logs them, but copied
  diagnostics or app logs may contain them).

You can expect an initial reply within a few days. Please give reasonable time
for a fix before disclosing publicly.

## How credentials are handled

- The access token, refresh token and their expiries are stored in the Home
  Assistant config entry (`/config/.storage`), never in the repository.
- With the account login method, the password is hashed locally with MD5 and
  only the digest is stored. The clear-text password is never persisted,
  logged or sent; the login request carries the digest.
- Tokens are never logged and never included in diagnostics.
- Only the fixed vendor origin `https://solar.siseli.com` is contacted;
  redirects are not followed.
- The refresh request carries the access token, the refresh token and a
  signature computed with the public web-portal application identity. The
  account password is never sent.
- The integration performs only two kinds of request: telemetry reads and
  session renewal. It never writes inverter settings.
