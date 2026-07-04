# Google Maps Platform — cost notes

Waypoint uses Google Maps Platform for its maps, search, and geocoding. This
page explains what gets billed, roughly how much, and — most importantly — how
to cap spending so a bug or a leaked key can't run up a surprise bill.

All prices are approximate **US list prices** and change over time. Always
confirm current rates in the
[pricing table](https://mapsplatform.google.com/pricing/) and the
[pricing calculator](https://mapsplatform.google.com/pricing/#calculator).
Google restructured Maps pricing in **March 2025**, replacing the old flat
$200/month credit with **per-product free monthly allotments**.

## What the app calls, and when

| Feature in Waypoint | Google API / SKU | ~Cost per 1,000 | Fires when… |
|---|---|---|---|
| Any page with a map (list, detail, add/edit form) | Maps JavaScript — Dynamic Map load | ~$7 | Every page load that shows a map |
| Location box + address search on the form | Places Autocomplete (session-based) | ~$17 per 1,000 sessions | Someone types a place and picks one |
| "Search nearby" + "Search this area" | Places Text Search | ~$32 | Every search and re-search |
| Open-now badge on the detail page | Place Details | ~$17 | Detail-page view of a waypoint with a Google Place ID |
| "Locate me", restoring a saved location, form address fallback | Geocoding | ~$5 | On locate, on load with a saved location, on manual address search |

**The two biggest drivers** are Dynamic Map loads (they happen on nearly every
page view) and Text Search (the priciest per call). The rest are minor.

## The reassuring part

For a self-hosted homelab app used by you and a handful of people, monthly
volume is tiny — likely a few hundred to a few thousand calls — which almost
certainly lands within the free monthly allotments, i.e. **$0**. The real risk
is not normal use; it's a bug or a leaked key generating calls.

## How to cap spending (do this when you set up the key)

1. **Restrict the API key** (Cloud Console → APIs & Services → Credentials →
   your key):
   - *Application restriction:* HTTP referrers → your Cloudflare Tunnel
     domain(s) only, e.g. `https://waypoint.example.com/*`. A browser map key
     is necessarily visible in page source, so this is what stops others from
     reusing it.
   - *API restriction:* limit the key to **Maps JavaScript API**, **Places
     API**, and **Geocoding API** only.
2. **Set daily quota caps** per API (APIs & Services → each API → Quotas). A
   hard daily ceiling is the single best guard — even a runaway loop can't
   exceed it. Set them low (e.g. a few hundred/day); your real usage is smaller.
3. **Set a billing budget alert** (Billing → Budgets & alerts) at ~$1–5 so
   you're emailed the moment anything unexpected happens.

## If usage ever grows

The biggest lever is reducing Dynamic Map loads: the detail and add/edit pages
each load a full interactive map. Options, in rough order of effort:

- Lazy-load the detail-page map only when the user clicks/scrolls to it.
- Use a Static Maps image instead of an interactive map where interaction isn't
  needed.
- Cache/debounce Text Search more aggressively.

None of this is worth doing at homelab scale — it's noted here only as the
lever to pull if traffic ever becomes significant.
