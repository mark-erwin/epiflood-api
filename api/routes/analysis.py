"""
analysis.py - Spatiotemporal analysis routes (placeholders).

Replaces the predictive-modeling routes. Statistics are computed in DuckDB
(corr(), window functions) so every number can be reproduced with plain SQL.
Each route returns a plain-text description of what it will do once implemented.
Mounted under /api/v1 in api.py.
"""

from datetime import date

from fastapi import APIRouter, Query
from fastapi.responses import PlainTextResponse

from core.constants import MW_MAX, MW_MIN, Disease

router = APIRouter(prefix="/analysis", tags=["Analysis"])


@router.get("/rainfall-lag", response_class=PlainTextResponse)
def rainfall_lag(
    disease: Disease,
    pcode: str | None = None,
    max_lag: int = Query(4, ge=0, le=12),
    year_from: int | None = Query(None, ge=2016, le=2100),
    year_to: int | None = Query(None, ge=2016, le=2100),
) -> str:
    return (
        "GET /api/v1/analysis/rainfall-lag\n"
        "\n"
        f"Received: disease={disease}, pcode={pcode}, max_lag={max_lag}, "
        f"year_from={year_from}, year_to={year_to}\n"
        "Expected: correlation between weekly rainfall and cases at lags 0..max_lag weeks. "
        "No pcode = all municipalities pooled.\n"
        "Source: rainfall_weekly (complete weeks only) joined with cases_weekly.\n"
        "Response: [{ lag_weeks, correlation, n_weeks }].\n"
        "Note: correlation is not causation; counts are small and reporting is uneven."
    )


@router.get("/hazard-exposure", response_class=PlainTextResponse)
def hazard_exposure(
    disease: Disease,
    hazard_level: int = Query(2, ge=1, le=3),
    year: int | None = Query(None, ge=2016, le=2100),
) -> str:
    return (
        "GET /api/v1/analysis/hazard-exposure\n"
        "\n"
        f"Received: disease={disease}, hazard_level={hazard_level}, year={year}\n"
        "Expected: how case counts relate to the share of each municipality in a flood-hazard "
        "level.\n"
        "Source: hazard_by_municipality joined with cases_weekly.\n"
        "Response: { correlation, n_municipalities, points: [{ pcode, municipality, "
        "hazard_pct, total_cases, mean_weekly_cases }] }."
    )


@router.get("/seasonality", response_class=PlainTextResponse)
def seasonality(
    disease: Disease,
    pcode: str | None = None,
    year_from: int | None = Query(None, ge=2016, le=2100),
    year_to: int | None = Query(None, ge=2016, le=2100),
) -> str:
    return (
        "GET /api/v1/analysis/seasonality\n"
        "\n"
        f"Received: disease={disease}, pcode={pcode}, year_from={year_from}, year_to={year_to}\n"
        "Expected: the typical yearly pattern: mean and median cases per morbidity week.\n"
        "Source: cases_weekly.\n"
        "Response: [{ mw, mean_cases, median_cases, p90_cases, years_observed }]."
    )


@router.get("/hotspots", response_class=PlainTextResponse)
def hotspots(
    disease: Disease,
    year: int | None = Query(None, ge=2016, le=2100),
    mw: int | None = Query(None, ge=MW_MIN, le=MW_MAX),
    baseline_years: int = Query(5, ge=1, le=10),
    as_of: date | None = None,
) -> str:
    return (
        "GET /api/v1/analysis/hotspots\n"
        "\n"
        f"Received: disease={disease}, year={year}, mw={mw}, baseline_years={baseline_years}, "
        f"as_of={as_of}\n"
        "Expected: municipalities whose cases for a week are well above their own historical "
        "baseline. Defaults to the latest reported week.\n"
        "Source: cases_weekly against the same-week baseline of the previous N years.\n"
        "Response: [{ pcode, municipality, cases, baseline_mean, baseline_std, z_score, "
        "ratio, is_hotspot }].\n"
        "Note: leptospirosis history is short, so its baseline is less reliable."
    )
