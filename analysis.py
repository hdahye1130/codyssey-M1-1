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
    report = f'''# 한국 태양광 발전량의 시계열 분석: 추세, 계절성 및 변동성 분석

> 분석 범위: KPX 전력시장 참여 태양광 발전기의 전력거래량(ESS 충·방전 포함). 한국 전체 태양광 발전량과 구분해야 합니다.

## 1. 분석 주제 및 선정 이유
태양광 발전량의 시간별 변화를 이해하면 에너지 저장과 전력 수급에서 변동성을 고려해야 하는 이유를 설명할 수 있습니다. 인증 없이 다운로드할 수 있는 공식 KPX 공개자료를 선택했습니다.

## 2. 분석 질문
1. 2025년 일별 발전량과 7일·30일 이동평균은 어떻게 변화하는가?
2. 월별 평균 일발전량은 어떻게 다르며 어느 달이 가장 높고 낮은가?
3. 일별 감소율과 7일 상대 변동성이 가장 큰 시점은 언제인가?

## 3. 데이터 설명
- 제공기관: 한국전력거래소(KPX), 공공데이터포털.
- 출처: [{SOURCE}]({SOURCE}) — 한국전력거래소_지역별 시간별 태양광 및 풍력 발전량_20251231.
- 수집일: 2026-10-03. 원본: `data/kpx_original.csv`(CP949 인코딩), 원본 SHA-256: `{quality['sha256']}`.
- 분석 기간: {quality['start']}~{quality['end']}, 한국 거래일 기준.
- 원본 {len(raw):,}행 중 태양광 {len(solar):,}행만 사용. 17개 지역을 합산해 시간별 {len(hourly):,}개, 일별 {len(daily):,}개 관측값 생성.
- 실제 컬럼: {', '.join(COLS)}. 단위는 MWh(1 GWh = 1,000 MWh).
- 날짜는 YYYY-MM-DD로 엄격하게 파싱. 거래시간 1~24는 같은 거래일의 24개 구간으로 취급하며 저장용 구간 시작 시각은 거래시간−1시간으로 표기합니다. 일별 집계는 원본 거래일로 수행합니다.
- 결측값: 태양광 원본 모든 컬럼 0개. 중복(거래일·시간·지역) 0개, 기대하는 날짜×24시간×17지역 조합의 누락 0개. 음수 및 비유한 발전량 0개.
- 이상치: 일별 발전량에 IQR(중간 50% 구간) 1.5배 기준을 적용했습니다. 범위 {lower:,.2f}~{upper:,.2f} MWh 밖의 후보는 {int(daily.iqr_flag.sum())}개입니다. 통계적 극단값이 측정 오류를 뜻하지 않으므로 삭제·보간하지 않았습니다. 지역별 시간값은 야간 0과 지역 규모 차이가 정상적이므로 일률적인 IQR 삭제를 하지 않았습니다.
- 이동평균/표준편차의 시작 6일 또는 29일과 변화율의 첫날은 계산에 필요한 이전 값이 없어 비어 있습니다. 원본 결측이 아니며 채우지 않았습니다.
- 한전 직접 거래·자가용 발전기는 제외됩니다. 소내 소비·주변압기 손실을 제외한 송전단 기준이며 수정정산으로 값이 바뀔 수 있습니다. 야간 소량 값은 ESS 방전에 따른 값일 수 있어 보존했습니다.

## 4. 분석 방법
- 일별 합계: 같은 거래일의 모든 지역·24시간 전력거래량을 합산.
- 이동평균: 당일과 이전 6일/29일의 평균. 단기 변화를 완화하고 기간 내 흐름을 확인합니다.
- 월별 집계: 월 합계와 평균 일발전량을 계산. 월별 일수 차이 영향을 줄이기 위해 비교 그래프는 평균 일발전량을 사용합니다.
- 일별 변화율: (당일/전일−1)×100. 야간 0이 많은 시간별 값 대신 양수인 일별 합계에 적용합니다.
- 변동성: 최근 7일 표본 표준편차(ddof=1)와 변동계수(CV=표준편차/평균×100). 발전량 수준이 다른 구간의 상대 변동성을 비교합니다.

## 5. 분석 결과 및 시각화
### 일별 추세
![일별 추세와 이동평균](images/01_trend.png)
일별 급변과 완만한 흐름을 함께 보기 위한 그래프입니다. 첫 30일 평균은 {first/1000:.3f} GWh/일, 마지막 30일은 {last/1000:.3f} GWh/일로 {facts['last_vs_first_pct']:+.2f}% 차이입니다. 양 끝 시점 비교만으로 장기 성장률을 의미하지는 않습니다.

### 월별 패턴
![월별 평균 일발전량](images/02_monthly.png)
월 길이 차이를 보정한 비교입니다. 최고는 {best}월 {monthly.loc[best,'mean']/1000:.3f} GWh/일, 최저는 {worst}월 {monthly.loc[worst,'mean']/1000:.3f} GWh/일입니다.

### 변화율과 변동성
![변화율과 상대 변동성](images/03_variability.png)
급격한 일별 변화와 여러 날에 걸친 불안정성을 구분하기 위한 그래프입니다. 최대 감소는 {drop_date.date()}의 {daily.loc[drop_date,'change_pct']:.2f}%, 최대 7일 CV는 {cv_date.date()}에 끝나는 구간의 {daily.loc[cv_date,'cv7_pct']:.2f}%입니다.

## 6. 인사이트
### 인사이트 1: 기간 내 흐름과 장기 추세는 구분해야 합니다
- 관찰(Fact): 첫 30일 대비 마지막 30일 평균은 {facts['last_vs_first_pct']:+.2f}% 차이입니다(그래프 1). 각각 {first/1000:.3f}, {last/1000:.3f} GWh/일입니다.
- 해석(Hypothesis): 계절·기상·설비 규모·시장 참여 변화가 함께 반영될 가능성이 있습니다. 현재 자료로 각각의 영향을 분리할 수 없습니다.
- 의미(Implication): 장기 증가/감소를 판단하려면 여러 해 같은 달과 설비용량을 함께 비교해야 합니다.

### 인사이트 2: 월별 발전량 차이가 큽니다
- 관찰(Fact): {best}월 평균은 {worst}월의 {facts['high_low_ratio']:.2f}배입니다(그래프 2). 최고 {monthly.loc[best,'mean']/1000:.3f}, 최저 {monthly.loc[worst,'mean']/1000:.3f} GWh/일입니다.
- 해석(Hypothesis): 일조 조건 및 기상과 관련될 가능성이 있지만 기상자료가 없어 원인을 증명하지 못합니다. 1년 자료는 반복 계절성의 증거로 충분하지 않습니다.
- 의미(Implication): 모든 달에 같은 발전량을 가정하기보다 월별 시나리오를 고려하고, 여러 해 자료로 반복 여부를 검증해야 합니다.

### 인사이트 3: 평균만으로 급변을 설명할 수 없습니다
- 관찰(Fact): {drop_date.date()} 발전량은 전일 {facts['drop_previous_mwh']/1000:.3f}에서 {facts['drop_mwh']/1000:.3f} GWh로 {facts['largest_drop_pct']:.2f}% 감소했습니다. {cv_date.date()}에 끝나는 7일 구간의 CV는 {facts['highest_cv7_pct']:.2f}%로 가장 높습니다(그래프 3).
- 해석(Hypothesis): 기상 변화나 운영 조건 변화 등이 관련되었을 수 있지만, 출력제어·기상·ESS 자료 없이 특정 원인으로 단정할 수 없습니다. 낮은 평균도 CV를 높일 수 있습니다. 가장 큰 증가율은 2025-02-13의 +749.80%이며 전날의 낮은 기준값이 비율을 크게 만들므로 증가율만으로 절대 발전량을 평가하지 않습니다.
- 의미(Implication): 에너지 저장·수급 계획은 평균과 함께 변동 폭을 고려해야 합니다. 이 분석만으로 필요한 배터리 용량이나 공급 부족을 계산할 수는 없습니다.

## 7. 결론
2025년의 월별 차이와 단기 급변을 수치로 확인했습니다. 이동평균은 흐름, 월별 평균은 기간 차이, 변화율·CV는 변동성을 보여줍니다. 분석 대상은 전력시장 참여 설비의 전력거래량이며 전국 총생산량으로 일반화하지 않습니다.

## 8. 한계점
1년으로 반복 계절성이나 장기 추세를 검증할 수 없습니다. 설비용량으로 정규화하지 않았으므로 발전량 증가가 효율 향상을 의미하지 않습니다. 기상·출력제어·ESS·지역별 설비용량을 분석하지 않았고 인과관계를 증명하지 않았습니다. 지역 합계는 지역 간 변동을 완화하며 전국 합계가 개별 발전소 특성을 대표하지 않습니다. 표준편차에는 추세와 계절 변화도 포함될 수 있습니다. 값은 수정정산될 수 있어 원본 파일과 해시를 함께 제공합니다.

## 9. AI 사용 로그
- AI를 사용한 작업: 공식 데이터 출처 탐색, 실제 CSV 컬럼 확인, 전처리·분석 Python 코드 작성, 실행 중 결과 확인, 그래프·보고서·README 작성, 제출 조건 점검.
- AI를 사용한 이유: 초보자의 반복적인 수동 코딩을 줄이고 분석과 제출물을 한 흐름으로 재현하기 위해 사용했습니다.
- 결과 검증 방법: 실제 코드를 실행하여 날짜·시간·지역 전체 조합, 결측·중복·음수를 검사했습니다. 원본 태양광 합계와 시간·일·월 집계 합계가 일치하는지 비교하고 첫 7일 이동평균을 원본 합계로 별도 계산하여 확인했습니다. 생성 PNG와 보고서 상대경로·필수 구조를 자동 확인합니다. 자동 검사 결과는 `data/validation.json`에 기록합니다. `verify.py`로 원본·코드만 별도 빈 폴더에 복사해 결과를 재생성하고 바이트 단위로 비교하며 결과는 `data/reproducibility.json`에 기록합니다. 이는 현재 Python 환경 내 검증이며 다른 운영체제에서 실행한 것은 아닙니다.
'''
    (ROOT/'REPORT.md').write_text(report,encoding='utf-8')
    (ROOT/'data/results.json').write_text(json.dumps({'quality':quality,'facts':facts},ensure_ascii=False,indent=2),encoding='utf-8')
    links = re.findall(r'!\[[^\]]*\]\(([^)]+)\)',report)
    assert len(links) >= 3
    for link in links:
        path = ROOT/link
        assert path.exists() and path.read_bytes().startswith(b'\x89PNG\r\n\x1a\n')
    checks = {'at_least_100_points':len(daily)>=100,'three_questions':all(f'{n}.' in report.split('## 3.')[0] for n in [1,2,3]),
        'at_least_two_methods':all(c in daily.columns for c in ['ma7_mwh','change_pct','std7_mwh']),'three_pngs':len(links)>=3,'three_insights':report.count('### 인사이트')>=3,
        'quality_explained':all(w in report for w in ['결측','이상치','중복']), 'source_and_period':SOURCE in report and quality['start'] in report and quality['end'] in report,'requirements_exists':(ROOT/'requirements.txt').exists(),
        'readme_exists':(ROOT/'README.md').exists() and 'python3 analysis.py' in (ROOT/'README.md').read_text(),'ai_log': '## 9. AI 사용 로그' in report,'image_links':True,
        'original_hourly_daily_monthly_totals_match':True,'first7_mean_independent_check':True,'time_grid_complete':missing_slots==0,
        'code_execution_success':True}
    assert all(checks.values()), checks
    (ROOT/'data/validation.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'facts':facts,'quality':quality,'checks':checks},ensure_ascii=False,indent=2))

if __name__ == '__main__':
    main()