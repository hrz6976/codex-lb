# Bark pool notifications

Source of truth: [pool-notifications](spec.md).

In **Settings → Bark notifications**, enter the device URL shown by Bark, such
as `https://api.day.app/YOUR_DEVICE_KEY`, and save. Self-hosted HTTP(S) servers
are supported. Administrators with security settings access can replace the URL
or disable delivery. The URL is stored encrypted and never returned by the API.
Changes apply on the next complete usage-refresh cycle without restarting.
Existing installations default to disabled.

The usage-refresh leader alerts when fresh, nonexpired standard quota windows
show exhaustion for all enabled accounts. Purchased credits are respected.
Paused, deactivated, reauthentication-required, and deletion-pending accounts
are excluded. Missing/stale data or an empty pool do not trigger an alert.
This does not monitor model-source capacity, per-key limits, or other routing
restrictions.

Successful delivery suppresses repeats until usable quota is observed again.
Failures retry on later refresh cycles with a ten-second timeout. Suppression
is process-local: a restart or leadership change can repeat an alert. Delivery
is not exactly-once. Only the account count is sent, never account names or keys.

For example, two enabled Plus accounts with exhausted seven-day quotas, future
resets, and no purchased credits produce one alert. Repeated polls stay silent.
Once either account recovers, a later exhaustion can produce another alert.

Protocol: [Bark V2 push API](https://github.com/Finb/bark-server/blob/master/docs/API_V2.md).
