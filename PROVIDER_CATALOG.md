# Provider catalog

UTTG uses at most seven provider integrations. A blank credential disables that credentialed provider; public feeds require an explicit enable flag. Fixed adapter paths are linked to primary provider documentation below.

| Provider ID | Data used | Configuration | Implementation status |
|---|---|---|---|
| `celestrak` | GP orbital elements | `UTTG_ENABLE_CELESTRAK=true` | active ingestion |
| `space-track` | satellite catalog | identity and password | active ingestion; local request budgets |
| `nasa-neows` | NEO objects and approaches | NASA provider credential | active ingestion |
| `noaa-swpc` | Kp and real-time solar wind | `UTTG_ENABLE_NOAA_SWPC=true` | active ingestion |
| `the-space-devs` | launch schedule | public flag or provider credential | active ingestion |
| `jpl-horizons` | Horizons vectors | `UTTG_ENABLE_JPL=true` | reviewed adapter; public endpoint disabled until canonical response mapping is complete |
| `esa` | none selected | disabled by default | intentionally unavailable until a specific official product API is selected |

Primary documentation: [CelesTrak GP](https://celestrak.org/NORAD/documentation/gp-data-formats.php), [Space-Track API](https://www.space-track.org/documentation), [NASA Open APIs](https://api.nasa.gov/), [NOAA SWPC data](https://www.swpc.noaa.gov/products-and-data), [Launch Library 2](https://ll.thespacedevs.com/2.2.0/), and [JPL Horizons](https://ssd-api.jpl.nasa.gov/doc/horizons.html).

Do not add a provider route by guessing a URL from examples or naming conventions. A change must cite primary documentation, freeze the base URL and path in the adapter, validate parameters through an allowlist, add recorded contract fixtures, and document attribution, quota, retention, redistribution, and commercial-use constraints.
