"""Read Google Maps Platform usage and cost for the current billing month.

Usage (call counts) comes from the Cloud Monitoring API; cost comes from a
BigQuery billing-export table. Both are optional: if the relevant settings
aren't configured, callers get an {"ok": False, "error": "not_configured"}
result and the admin page shows setup instructions instead of erroring.

Everything network-facing is wrapped so a misconfiguration or transient API
error surfaces as a readable message on the page rather than a 500.
"""
import datetime

from django.conf import settings
from django.core.cache import cache

# Backend service names Maps Platform reports usage under, mapped to labels.
MAPS_SERVICES = {
    "maps-backend.googleapis.com": "Maps JavaScript / Dynamic Maps",
    "places-backend.googleapis.com": "Places API",
    "places.googleapis.com": "Places API (New)",
    "geocoding-backend.googleapis.com": "Geocoding API",
    "static-maps-backend.googleapis.com": "Maps Static API",
    "maps-embed-backend.googleapis.com": "Maps Embed API",
}

CACHE_TTL = 3600  # 1 hour — these calls are slow and BigQuery scans cost money
_SCOPES = [
    "https://www.googleapis.com/auth/monitoring.read",
    "https://www.googleapis.com/auth/bigquery.readonly",
]


def project_id():
    return getattr(settings, "GCP_PROJECT_ID", "") or ""


def credentials_file():
    return getattr(settings, "GCP_CREDENTIALS_FILE", "") or ""


def billing_table():
    return getattr(settings, "GCP_BILLING_BQ_TABLE", "") or ""


def usage_configured():
    return bool(project_id() and credentials_file())


def cost_configured():
    return bool(usage_configured() and billing_table())


def month_key():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m")


def _month_bounds():
    now = datetime.datetime.now(datetime.timezone.utc)
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return start, now


def _session():
    from google.oauth2 import service_account
    from google.auth.transport.requests import AuthorizedSession
    creds = service_account.Credentials.from_service_account_file(
        credentials_file(), scopes=_SCOPES
    )
    return AuthorizedSession(creds)


def clear_cache():
    cache.delete("gcp_usage_" + month_key())
    cache.delete("gcp_cost_" + month_key())


# ── Usage (Cloud Monitoring) ───────────────────────────────────────────────────

def get_usage():
    key = "gcp_usage_" + month_key()
    cached = cache.get(key)
    if cached is not None:
        return cached
    result = _fetch_usage()
    if result.get("ok"):
        cache.set(key, result, CACHE_TTL)
    return result


def _fetch_usage():
    if not usage_configured():
        return {"ok": False, "error": "not_configured"}
    try:
        sess = _session()
        start, end = _month_bounds()
        svc_filter = " OR ".join(f'resource.labels.service="{s}"' for s in MAPS_SERVICES)
        params = {
            "filter": (
                'metric.type="serviceruntime.googleapis.com/api/request_count" '
                f"AND ({svc_filter})"
            ),
            "interval.startTime": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "interval.endTime": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "aggregation.alignmentPeriod": "86400s",
            "aggregation.perSeriesAligner": "ALIGN_SUM",
            "aggregation.crossSeriesReducer": "REDUCE_SUM",
            "aggregation.groupByFields": "resource.labels.service",
            "view": "FULL",
        }
        url = f"https://monitoring.googleapis.com/v3/projects/{project_id()}/timeSeries"
        merged = {}
        page_token = None
        while True:
            if page_token:
                params["pageToken"] = page_token
            resp = sess.get(url, params=params, timeout=30)
            if resp.status_code != 200:
                return {"ok": False, "error": f"Monitoring API {resp.status_code}: {resp.text[:300]}"}
            body = resp.json()
            for ts in body.get("timeSeries", []):
                svc = ts.get("resource", {}).get("labels", {}).get("service", "unknown")
                total = 0
                for p in ts.get("points", []):
                    v = p.get("value", {})
                    total += int(float(v.get("int64Value", v.get("doubleValue", 0)) or 0))
                entry = merged.setdefault(
                    svc, {"service": svc, "label": MAPS_SERVICES.get(svc, svc), "calls": 0}
                )
                entry["calls"] += total
            page_token = body.get("nextPageToken")
            if not page_token:
                break
        rows = sorted(merged.values(), key=lambda r: -r["calls"])
        return {"ok": True, "rows": rows, "total": sum(r["calls"] for r in rows)}
    except ModuleNotFoundError:
        return {"ok": False, "error": "libraries_missing"}
    except (KeyboardInterrupt, SystemExit):
        raise
    except BaseException as e:  # noqa: BLE001 — this boundary must never raise
        # Catches even non-Exception failures (e.g. native-lib panics) so the
        # admin page always renders an error message instead of a 500.
        return {"ok": False, "error": str(e)[:300]}


# ── Cost (BigQuery billing export) ─────────────────────────────────────────────

def get_cost():
    key = "gcp_cost_" + month_key()
    cached = cache.get(key)
    if cached is not None:
        return cached
    result = _fetch_cost()
    if result.get("ok"):
        cache.set(key, result, CACHE_TTL)
    return result


def _fetch_cost():
    if not cost_configured():
        return {"ok": False, "error": "not_configured"}
    try:
        sess = _session()
        sql = (
            "SELECT sku.description AS sku, "
            "ROUND(SUM(cost), 2) AS gross, "
            "ROUND(SUM(cost) + SUM(IFNULL("
            "(SELECT SUM(c.amount) FROM UNNEST(credits) c), 0)), 2) AS net, "
            "ANY_VALUE(currency) AS currency "
            f"FROM `{billing_table()}` "
            "WHERE service.description LIKE '%Maps%' "
            "AND invoice.month = FORMAT_DATE('%Y%m', CURRENT_DATE()) "
            "GROUP BY sku ORDER BY net DESC"
        )
        url = f"https://bigquery.googleapis.com/bigquery/v2/projects/{project_id()}/queries"
        resp = sess.post(
            url, json={"query": sql, "useLegacySql": False, "timeoutMs": 25000}, timeout=40
        )
        if resp.status_code != 200:
            return {"ok": False, "error": f"BigQuery API {resp.status_code}: {resp.text[:300]}"}
        body = resp.json()
        if not body.get("jobComplete", False):
            return {"ok": False, "error": "BigQuery job still running; try refreshing shortly."}
        fields = [f["name"] for f in body.get("schema", {}).get("fields", [])]
        rows = []
        for row in body.get("rows", []):
            rec = dict(zip(fields, [c.get("v") for c in row.get("f", [])]))
            rows.append({
                "sku": rec.get("sku"),
                "gross": float(rec.get("gross") or 0),
                "net": float(rec.get("net") or 0),
                "currency": rec.get("currency") or "USD",
            })
        return {
            "ok": True,
            "rows": rows,
            "gross_total": round(sum(r["gross"] for r in rows), 2),
            "net_total": round(sum(r["net"] for r in rows), 2),
            "currency": rows[0]["currency"] if rows else "USD",
        }
    except ModuleNotFoundError:
        return {"ok": False, "error": "libraries_missing"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)[:300]}
