"""Derive season and weather-proxy insights from daily KPX energy and 2025 ERA5 samples.

Weather data are mean conditions at 17 representative sites, NOT weather measured
at all Korean solar plants. Cloud groups: clear <=35%, mixed >35% and <65%,
cloudy >=65%. Interpret associations, not causal effects.
"""
from pathlib import Path
import numpy as np
import pandas as pd

SEASON_ORDER = ["Winter", "Spring", "Summer", "Autumn"]
CLOUD_ORDER = ["clear", "partly", "cloudy"]


def season_of(month):
    if month in (12, 1, 2):
        return "Winter"
    if month in (3, 4, 5):
        return "Spring"
    if month in (6, 7, 8):
        return "Summer"
    return "Autumn"


def bar_svg(title, subtitle, rows, footer):
    """Minimal, deterministic vector chart for GitHub Markdown."""
    lines = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="920" height="430" viewBox="0 0 920 430">',
        '<rect width="920" height="430" fill="#ffffff"/>',
        f'<text x="36" y="48" font-family="Arial, sans-serif" font-size="26" font-weight="700" fill="#14283f">{title}</text>',
        f'<text x="36" y="77" font-family="Arial, sans-serif" font-size="16" fill="#46596f">{subtitle}</text>',
    ]
    for i, (label, value, color) in enumerate(rows):
        y = 145 + i * 64
        width = value * 11
        lines.append(f'<text x="42" y="{y}" font-family="Arial, sans-serif" font-size="18" fill="#14283f">{label}</text>')
        lines.append(f'<rect x="225" y="{y-28}" width="{width:.1f}" height="38" rx="7" fill="{color}"/>')
        lines.append(f'<text x="{225+width+14:.1f}" y="{y-1}" font-family="Arial, sans-serif" font-size="18" font-weight="700" fill="#14283f">{value:.2f}</text>')
    lines.append(f'<text x="36" y="408" font-family="Arial, sans-serif" font-size="14" fill="#46596f">{footer}</text>')
    lines.append('</svg>')
    return "\n".join(lines) + "\n"


def build_new_insights(daily, root):
    root = Path(root)
    weather_file = root / "data/daily_weather_2025.csv"
    if not weather_file.exists():
        raise FileNotFoundError("Missing committed daily weather proxy: " + str(weather_file))
    weather = pd.read_csv(weather_file, comment="#", parse_dates=["date"])
    assert len(weather) == 365 and weather["date"].is_unique, "Weather must cover 365 unique dates"
    required = ["cloud_cover_mean_pct", "precipitation_mean_mm", "sunshine_mean_hours"]
    assert weather[required].notna().all().all(), "Weather values are missing"
    assert weather["cloud_cover_mean_pct"].between(0, 100).all()
    assert weather["precipitation_mean_mm"].ge(0).all()
    weather = weather.set_index("date").sort_index()
    assert daily.index.equals(weather.index), "Weather and energy must share dates"
    expected_group = np.where(weather.cloud_cover_mean_pct <= 35, "clear",
                         np.where(weather.cloud_cover_mean_pct >= 65, "cloudy", "partly"))
    assert (weather.cloud_group.to_numpy() == expected_group).all(), "Cloud groups do not match thresholds"

    combined = daily[["energy_mwh"]].join(weather)
    combined["season"] = [season_of(m) for m in combined.index.month]
    combined["gwh_day"] = combined.energy_mwh / 1000
    season = combined.groupby("season").gwh_day.agg(["count", "mean"]).reindex(SEASON_ORDER)
    cloud = combined.groupby("cloud_group").gwh_day.agg(["count", "mean"]).reindex(CLOUD_ORDER)
    assert not season.isna().any().any() and not cloud.isna().any().any()
    by_season = combined.groupby(["season", "cloud_group"]).gwh_day.agg(["count", "mean"])
    # Check the same directional relationship within each season.
    assert all(by_season.loc[(s, "clear"), "mean"] > by_season.loc[(s, "cloudy"), "mean"]
               for s in SEASON_ORDER)

    rain = combined.groupby(combined.precipitation_mean_mm >= 1).gwh_day.agg(["count", "mean"])
    corr = combined[["cloud_cover_mean_pct", "gwh_day"]].corr().iloc[0, 1]
    assert np.isfinite(corr)
    (root / "data/seasonal_summary.csv").write_text(
        "season,days,mean_gwh_per_day\n" +
        "".join(f"{s},{int(season.loc[s, 'count'])},{season.loc[s, 'mean']:.3f}\n"
                for s in SEASON_ORDER), encoding="utf-8")
    (root / "data/cloud_summary.csv").write_text(
        "cloud_group,days,mean_gwh_per_day\n" +
        "".join(f"{g},{int(cloud.loc[g, 'count'])},{cloud.loc[g, 'mean']:.3f}\n"
                for g in CLOUD_ORDER), encoding="utf-8")

    (root / "images/04_seasons.svg").write_text(bar_svg(
        "Solar energy by season (2025)", "Mean daily energy (GWh/day) | KPX traded solar",
        [(s, float(season.loc[s, "mean"]), "#147d85" if s == "Summer" else "#a7cfd1")
         for s in SEASON_ORDER],
        "Season: Winter=Dec-Feb, Spring=Mar-May, Summer=Jun-Aug, Autumn=Sep-Nov"
    ), encoding="utf-8")
    (root / "images/05_cloud_weather.svg").write_text(bar_svg(
        "Solar energy by cloudiness (2025)", "Mean daily energy (GWh/day) | 17-site cloud proxy",
        [(label, float(cloud.loc[group, "mean"]), color) for group, label, color in [
            ("clear", "Cloud <=35%", "#e7a13f"),
            ("partly", "Cloud 35-65%", "#69a9b0"),
            ("cloudy", "Cloud >=65%", "#74879c")]],
        "Cloudiness is an equal-weight ERA5 site average, not plant-level weather."
    ), encoding="utf-8")
    return {
        "season_mean_gwh_day": {s: round(float(season.loc[s, "mean"]), 3) for s in SEASON_ORDER},
        "season_days": {s: int(season.loc[s, "count"]) for s in SEASON_ORDER},
        "cloud_mean_gwh_day": {g: round(float(cloud.loc[g, "mean"]), 3) for g in CLOUD_ORDER},
        "cloud_days": {g: int(cloud.loc[g, "count"]) for g in CLOUD_ORDER},
        "cloud_clear_vs_cloudy_pct": round((cloud.loc["clear", "mean"] / cloud.loc["cloudy", "mean"] - 1) * 100, 2),
        "cloud_energy_pearson_r": round(float(corr), 3),
        "rainy_days_ge_1mm": int(rain.loc[True, "count"]),
        "rainy_mean_gwh_day": round(float(rain.loc[True, "mean"]), 3),
        "dry_mean_gwh_day": round(float(rain.loc[False, "mean"]), 3),
        "within_season_clear_gt_cloudy": True
    }
