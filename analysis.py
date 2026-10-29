"""KPX official 2025 solar market-traded energy analysis. Run: python analysis.py"""
from pathlib import Path
import hashlib
import json
import re
import argparse
import urllib.request
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent
SOURCE = 'https://www.data.go.kr/data/15065269/fileData.do'
DOWNLOAD = 'https://www.data.go.kr/cmm/cmm/fileDownload.do?atchFileId=FILE_000000003630221&fileDetailSn=1&insertDataPrcus=N'
COLS = ['거래일', '거래시간', '지역', '연료원', '전력거래량(MWh)']

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--download', action='store_true', help='Download pinned official original file again')
    args = parser.parse_args()
    for folder in ['data', 'images']:
        (ROOT / folder).mkdir(exist_ok=True)
    raw_path = ROOT / 'data/kpx_original.csv'
    if args.download or not raw_path.exists():
        request = urllib.request.Request(DOWNLOAD, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(request, timeout=60) as response:
            content = response.read()
        # Do not overwrite the bundled input with an HTML error or unrelated binary file.
        if b'%PDF' == content[:4] or b'<html' in content[:500].lower():
            raise ValueError('Download is not the expected CSV. Use the official source page.')
        candidate = ROOT / 'data/download_candidate.csv'
        candidate.write_bytes(content)
        try:
            probe = pd.read_csv(candidate, encoding='cp949')
            if list(probe.columns) != COLS or len(probe) != 166440:
                raise ValueError('Official download schema/row count changed; review before replacing bundled data.')
            candidate.replace(raw_path)
        finally:
            candidate.unlink(missing_ok=True)
    raw = pd.read_csv(raw_path, encoding='cp949')
    if list(raw.columns) != COLS:
        raise ValueError(f'Unexpected actual columns: {list(raw.columns)}')
    solar = raw.loc[raw['연료원'].eq('태양광')].copy()
    nulls = solar.isna().sum().to_dict()
    duplicates = int(solar.duplicated(['거래일', '거래시간', '지역']).sum())
    solar['date'] = pd.to_datetime(solar['거래일'], format='%Y-%m-%d', errors='raise')
    solar['energy_mwh'] = pd.to_numeric(solar['전력거래량(MWh)'], errors='raise')
    assert solar['거래시간'].between(1, 24).all(), 'Trading hour must be 1–24'
    assert not duplicates and not any(nulls.values()), 'Missing/duplicate records need explicit review'
    assert np.isfinite(solar['energy_mwh']).all() and solar['energy_mwh'].ge(0).all()
    # Hour labels denote 24 trading periods; keep original trade date for daily totals.
    solar['period_start_kst'] = solar['date'] + pd.to_timedelta(solar['거래시간'] - 1, unit='h')
    solar = solar.sort_values(['date', '거래시간', '지역'])
    dates = pd.date_range('2025-01-01', '2025-12-31', freq='D')
    regions = sorted(solar['지역'].unique())
    expected = pd.MultiIndex.from_product([dates, range(1, 25), regions], names=['date','거래시간','지역'])
    actual = pd.MultiIndex.from_frame(solar[['date','거래시간','지역']])
    missing_slots = len(expected.difference(actual))
    extra_slots = len(actual.difference(expected))
    assert len(regions) == 17 and missing_slots == 0 and extra_slots == 0, 'Incomplete regional time grid'
    hourly = solar.groupby('period_start_kst')['energy_mwh'].sum().rename('energy_mwh').to_frame()
    daily = solar.groupby('date')['energy_mwh'].sum().reindex(dates).rename('energy_mwh').to_frame()
    daily.index.name = 'date'
    assert daily['energy_mwh'].notna().all() and len(daily) >= 100
    daily['ma7_mwh'] = daily['energy_mwh'].rolling(7, min_periods=7).mean()
    daily['ma30_mwh'] = daily['energy_mwh'].rolling(30, min_periods=30).mean()
    daily['change_pct'] = daily['energy_mwh'].pct_change(fill_method=None) * 100
    daily['std7_mwh'] = daily['energy_mwh'].rolling(7, min_periods=7).std(ddof=1)
    daily['cv7_pct'] = daily['std7_mwh'] / daily['ma7_mwh'] * 100
    q1, q3 = daily['energy_mwh'].quantile([.25, .75])
    lower, upper = q1 - 1.5*(q3-q1), q3 + 1.5*(q3-q1)
    daily['iqr_flag'] = ~daily['energy_mwh'].between(lower, upper)
    monthly = daily.groupby(daily.index.month)['energy_mwh'].agg(['count','sum','mean','std'])
    monthly.index.name = 'month'
    monthly['cv_pct'] = monthly['std'] / monthly['mean'] * 100
    hourly.to_csv(ROOT / 'data/hourly_solar.csv', float_format='%.9f')
    daily.to_csv(ROOT / 'data/daily_solar.csv', float_format='%.9f')
    monthly.to_csv(ROOT / 'data/monthly_summary.csv', float_format='%.9f')
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11, 'axes.spines.top':False,'axes.spines.right':False})
    fig, ax = plt.subplots(figsize=(11,4.6))
    ax.plot(daily.index, daily.energy_mwh/1000, color='#bcc5d2', lw=1, label='Daily energy')
    ax.plot(daily.index, daily.ma7_mwh/1000, color='#247e95', lw=1.5, label='7-day trailing mean')
    ax.plot(daily.index, daily.ma30_mwh/1000, color='#de8c25', lw=2, label='30-day trailing mean')
    ax.set(title='Korea solar market-traded energy: daily trend (2025)', xlabel='Trade date (KST)', ylabel='Daily energy (GWh)')
    ax.legend();ax.grid(alpha=.2);fig.tight_layout();fig.savefig(ROOT/'images/01_trend.png',dpi=180);plt.close(fig)
    fig, ax = plt.subplots(figsize=(10,4.6))
    ax.bar(monthly.index, monthly['mean']/1000, color='#247e95')
    ax.set(title='Monthly mean daily solar market-traded energy (2025)',xlabel='Month',ylabel='Mean daily energy (GWh/day)',xticks=range(1,13))
    ax.grid(axis='y',alpha=.2);fig.tight_layout();fig.savefig(ROOT/'images/02_monthly.png',dpi=180);plt.close(fig)
    fig, axes = plt.subplots(2,1,figsize=(11,7),sharex=True)
    axes[0].plot(daily.index,daily.change_pct,color='#247e95',lw=.8)
    axes[0].axhline(0,color='gray',lw=.8);axes[0].set(title='Daily changes and rolling variability (2025)',ylabel='Day-over-day change (%)')
    axes[1].plot(daily.index,daily.cv7_pct,color='#de8c25',lw=1.3)
    axes[1].set(xlabel='Trade date (KST)',ylabel='7-day coefficient of variation (%)')
    for ax in axes:ax.grid(alpha=.2)
    fig.tight_layout();fig.savefig(ROOT/'images/03_variability.png',dpi=180);plt.close(fig)
    best, worst = int(monthly['mean'].idxmax()), int(monthly['mean'].idxmin())
    first, last = daily.iloc[:30].energy_mwh.mean(), daily.iloc[-30:].energy_mwh.mean()
    cv_date = daily.cv7_pct.idxmax(); drop_date = daily.change_pct.idxmin()
    rise_date = daily.change_pct.idxmax()
    facts = {'first30_mean_mwh':first,'last30_mean_mwh':last,'last_vs_first_pct':(last/first-1)*100,
             'highest_mean_month':best,'highest_month_mean_mwh':monthly.loc[best,'mean'],
             'lowest_mean_month':worst,'lowest_month_mean_mwh':monthly.loc[worst,'mean'],
             'high_low_ratio':monthly.loc[best,'mean']/monthly.loc[worst,'mean'],
             'highest_cv7_date':str(cv_date.date()),'highest_cv7_pct':daily.loc[cv_date,'cv7_pct'],
             'largest_drop_date':str(drop_date.date()),'largest_drop_pct':daily.loc[drop_date,'change_pct'],
             'drop_previous_mwh':daily.loc[drop_date-pd.Timedelta(days=1),'energy_mwh'],'drop_mwh':daily.loc[drop_date,'energy_mwh'],
             'largest_rise_date':str(rise_date.date()),'largest_rise_pct':daily.loc[rise_date,'change_pct']}
    quality = {'raw_rows':len(raw),'solar_rows':len(solar),'hourly_points':len(hourly),'daily_points':len(daily),
       'start':str(daily.index.min().date()),'end':str(daily.index.max().date()),'regions':regions,
       'columns':COLS,'source_missing':{k:int(v) for k,v in nulls.items()},'duplicate_keys':duplicates,
       'missing_expected_slots':missing_slots,'extra_slots':extra_slots,'negative_energy':int(solar.energy_mwh.lt(0).sum()),
       'daily_iqr_lower_mwh':lower,'daily_iqr_upper_mwh':upper,'daily_iqr_flags':int(daily.iqr_flag.sum()),
       'derived_warmup_missing':{'ma7':6,'ma30':29,'change_pct':1,'std7':6,'cv7':6},
       'sha256':hashlib.sha256(raw_path.read_bytes()).hexdigest()}
    # Independent sum checks: original solar total == hourly == daily == monthly.
    totals = [solar.energy_mwh.sum(), hourly.energy_mwh.sum(), daily.energy_mwh.sum(),monthly['sum'].sum()]
    assert np.allclose(totals, totals[0], rtol=1e-12, atol=1e-6)
    direct_first7 = solar.loc[solar.date.between(dates[0],dates[6]),'energy_mwh'].sum()/7
    assert np.isclose(direct_first7,daily.iloc[6].ma7_mwh)
    # REPORT.md is a human-reviewed interpretation, not a generated claim.
    # Numeric/graphic evidence is reproducibly generated from the CSV inputs.
    from insight_extension import build_new_insights
    facts.update(build_new_insights(daily, ROOT))
    report_path = ROOT / 'REPORT.md'
    report = report_path.read_text(encoding='utf-8')
    (ROOT/'data/results.json').write_text(json.dumps({'quality':quality,'facts':facts},ensure_ascii=False,indent=2),encoding='utf-8')
    links = re.findall(r'!\[[^\]]*\]\(([^)]+)\)',report)
    assert len(links) >= 3
    for link in links:
        path = ROOT/link
        assert path.exists() and (
            path.read_bytes().startswith(b'\\x89PNG\\r\\n\\x1a\\n')
            if path.suffix.lower() == '.png' else
            (path.suffix.lower() == '.svg' and path.read_text(encoding='utf-8').startswith('<svg '))
        )
    checks = {'at_least_100_points':len(daily)>=100,'three_questions':all(f'{n}.' in report.split('## 3.')[0] for n in [1,2,3]),
        'at_least_two_methods':all(c in daily.columns for c in ['ma7_mwh','change_pct','std7_mwh']),'three_pngs':sum(str(x).lower().endswith('.png') for x in links)>=3,'five_visualizations':len(links)>=5,'season_weather_analysis':all(k in facts for k in ['season_mean_gwh_day','cloud_mean_gwh_day','cloud_energy_pearson_r']),'three_insights':report.count('### 인사이트')>=3,
        'quality_explained':all(w in report for w in ['결측','이상치','중복']), 'source_and_period':SOURCE in report and quality['start'] in report and quality['end'] in report,'requirements_exists':(ROOT/'requirements.txt').exists(),
        'readme_exists':(ROOT/'README.md').exists() and 'python3 analysis.py' in (ROOT/'README.md').read_text(),'ai_log': '## 9. AI 사용 로그' in report,'image_links':True,
        'original_hourly_daily_monthly_totals_match':True,'first7_mean_independent_check':True,'time_grid_complete':missing_slots==0,
        'code_execution_success':True}
    assert all(checks.values()), checks
    (ROOT/'data/validation.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'facts':facts,'quality':quality,'checks':checks},ensure_ascii=False,indent=2))

if __name__ == '__main__':
    main()