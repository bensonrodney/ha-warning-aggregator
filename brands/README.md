# Brand assets

Since Home Assistant **2026.3**, a custom integration ships its own brand
images — no `home-assistant/brands` PR needed. HA serves them from
`custom_components/<domain>/brand/` via its local brands proxy, and they take
priority over the CDN. See the
[Brands Proxy API announcement](https://developers.home-assistant.io/blog/2026/02/24/brands-proxy-api).

`generate_logo.py` writes two places from one design:

- **`../custom_components/warning_aggregator/brand/`** — `icon.png`, `logo.png`,
  `dark_logo.png`. What HA and HACS actually serve; shipped in the release zip.
  (HACS's `brands` validation check also just looks for `brand/icon.png` here.)
- **`custom_integrations/warning_aggregator/`** (this folder) — the full set at
  [`home-assistant/brands`](https://github.com/home-assistant/brands) sizes, kept
  only in case a PR there is ever wanted (e.g. to also cover non-custom installs).

## Files

| File | Size | |
| --- | --- | --- |
| `icon.png` / `icon@2x.png` | 256² / 512² | square mark |
| `logo.png` / `logo@2x.png` | ≤512 wide | full lockup, light |
| `dark_logo.png` / `dark_logo@2x.png` | ≤512 wide | full lockup, dark |

Regenerate:

```bash
uv run --no-project --with pillow brands/generate_logo.py
```
