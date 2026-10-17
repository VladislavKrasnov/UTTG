# Provider catalog

UTTG uses at most seven provider integrations. A blank credential disables that credentialed provider; public feeds require an explicit enable flag. Fixed adapter paths are linked to primary provider documentation below.

| Provider ID | Data used | Configuration | Implementation status |
|---|---|---|---|
| `celestrak` | GP orbital elements in TLE format, group `active` every 2 h | `UTTG_ENABLE_CELESTRAK=true` | active ingestion; the "not updated since your last download" reply is treated as unchanged data |
| `space-track` | satellite catalog | identity and password | active ingestion; local request budgets |
| `noaa-swpc` | 1-minute estimated Kp and active-source real-time solar wind | `UTTG_ENABLE_NOAA_SWPC=true` | active ingestion |
| `jpl-ssd` | close approaches (CAD API), PHA and Sentry flags | `UTTG_ENABLE_JPL=true` | active ingestion, primary NEO source |
| `nasa-neows` | NEO objects and approaches | NASA provider credential | optional; `api.nasa.gov` answers 403 from some regions |
| `the-space-devs` | launch schedule with pad coordinates (LL2 2.3.0) | public flag or `UTTG_THE_SPACE_DEVS_API_KEY` sent as `Authorization: Token` | first launch source; unreachable from some networks |
| `rocketlaunch-live` | next five launches with operator, vehicle, pad, weather | `UTTG_ENABLE_ROCKETLAUNCH_LIVE=true` | fallback launch source |
| `esa` | none selected | disabled by default | intentionally unavailable until a specific official product API is selected |

Launch ingestion tries `the-space-devs`, then `rocketlaunch-live`; the first source that answers replaces the set of future launches in one transaction, so switching sources never leaves duplicates. Set `UTTG_HTTP_PROXY` to route provider traffic through a proxy; direct connections remain the fallback.

Primary documentation: [CelesTrak GP](https://celestrak.org/NORAD/documentation/gp-data-formats.php), [Space-Track API](https://www.space-track.org/documentation), [NOAA SWPC data](https://www.swpc.noaa.gov/products-and-data), [JPL CAD API](https://ssd-api.jpl.nasa.gov/doc/cad.html), [JPL Sentry API](https://ssd-api.jpl.nasa.gov/doc/sentry.html), [NASA Open APIs](https://api.nasa.gov/), [Launch Library 2](https://ll.thespacedevs.com/docs/), and [RocketLaunch.Live API](https://www.rocketlaunch.live/api).

Do not add a provider route by guessing a URL from examples or naming conventions. A change must cite primary documentation, freeze the base URL and path in the adapter, validate parameters through an allowlist, add recorded contract fixtures, and document attribution, quota, retention, redistribution, and commercial-use constraints.
