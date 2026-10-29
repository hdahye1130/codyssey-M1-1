# M1-1 — 한국 태양광 발전량은 언제, 어떤 날씨에서 가장 많은가?

2025년 **KPX 전력시장 참여 태양광 설비의 전력거래량**을 대상으로, **계절별·월별·구름량별 평균 발전량**과 일별 급변을 분석합니다.

**보고서:** [REPORT.md](REPORT.md) — 발표에 필요한 관찰·해석·의미(인사이트 4개)를 정리했습니다.

## 빠른 결과

- **계절별 최고:** 여름(6~8월) 41.334GWh/일, 최저 겨울(12~2월) 27.001GWh/일
- **월별 최고:** 4월 44.272GWh/일, 최저 1월 23.476GWh/일
- **구름량별:** 17개 지역 대표 지점의 평균 구름량 ≤35%인 날 42.827GWh/일, ≥65%인 날 27.075GWh/일
- 기상 분류는 기상청 공식 예보가 아닌 **분석용 ERA5 구름량 기준**입니다. 비교 자료가 전국 모든 발전소의 날씨를 대표하거나 원인을 증명하지는 않습니다.

## 그래프

1. [일별 추세와 이동평균](images/01_trend.png)
2. [월별 평균](images/02_monthly.png)
3. [변화율과 변동성](images/03_variability.png)
4. [계절별 평균](images/04_seasons.svg)
5. [구름량별 평균](images/05_cloud_weather.svg)

## 설치 및 실행

Python 3.11 또는 3.12를 권장합니다. 저장소 폴더에서 터미널을 열고 순서대로 실행합니다.

```bash
python3 -m pip install -r requirements.txt
python3 analysis.py
python3 verify.py
```

Windows에서는 `python3` 대신 `python`을 사용해도 됩니다.

- `analysis.py`는 `data/kpx_original.csv`가 없으면 KPX 원본 데이터를 자동으로 받습니다. KPX 자료 다운로드에는 계정 또는 API 키가 필요하지 않습니다.
- 기존 KPX 데이터 품질검사와 일별·월별 이동평균/변동성 계산을 유지합니다.
- `insight_extension.py`가 **이미 저장된** `data/daily_weather_2025.csv`와 발전량을 날짜별로 결합해 계절·구름량 요약 CSV 및 SVG 그래프를 다시 생성합니다.
- `REPORT.md`는 수치를 검토해 작성한 **설명 문서**이므로 분석 코드가 자동으로 덮어쓰지 않습니다. 입력 자료가 바뀌면 보고서의 수치도 직접 재검토해야 합니다.
- `verify.py`는 임시 폴더에서 데이터를 재생성해 그래프/집계/검증 결과를 비교합니다. 실행하기 전에는 최신 재현성 확인을 주장하지 않습니다.

## 데이터 출처 및 수집 방법

### 1. 태양광 발전량: KPX
- 원본 페이지: https://www.data.go.kr/data/15065269/fileData.do
- 데이터명: 한국전력거래소_지역별 시간별 태양광 및 풍력 발전량_20251231
- 수집일: 2026-10-03, 분석 기간: 2025-01-01~2025-12-31
- 원본은 CP949 CSV, 166,440행. 태양광 148,920행(17지역 × 24시간 × 365일) 사용.
- 컬럼: 거래일, 거래시간, 지역, 연료원, 전력거래량(MWh).
- 원본 파일 크기 때문에 GitHub에 넣지 않고 `analysis.py`가 다시 수집합니다. `python3 analysis.py --download`로 재수집할 수도 있습니다. 예상 열·행 수가 다르면 교체하지 않고 오류를 냅니다.
- 한전 직접 거래 및 자가용 설비는 제외됩니다. ESS 충·방전 및 수정정산 효과가 포함될 수 있습니다.

### 2. 날씨: Open-Meteo Historical Weather API / ERA5
- 문서: https://open-meteo.com/en/docs/historical-weather-api
- 원 출처: [ERA5 reanalysis](https://www.ecmwf.int/en/forecasts/dataset/ecmwf-reanalysis-v5), Open-Meteo를 통해 취득.
- 변수: `cloud_cover_mean`(%), `precipitation_sum`(mm), `sunshine_duration`(초 → 시간).
- 날짜: 2025-01-01~2025-12-31, `timezone=Asia/Seoul`, `models=era5`.
- 아래 각 행은 **지역 대표 1개 지점의 대략적인 좌표**입니다. 행 순서대로 위도·경도를 API에 넣고 동일 날짜의 각 지표를 **17개 지점 단순 평균**해 `data/daily_weather_2025.csv`에 저장했습니다.
- API 키 없이 다시 조회할 수 있습니다. Open-Meteo의 데이터 출처 및 [라이선스](https://open-meteo.com/en/terms) 조건을 준수해야 합니다.

| 대표 지점 | 위도 | 경도 |
|---|---:|---:|
| 서울 | 37.5665 | 126.9780 |
| 부산 | 35.1796 | 129.0756 |
| 대구 | 35.8714 | 128.6014 |
| 인천 | 37.4563 | 126.7052 |
| 광주 | 35.1595 | 126.8526 |
| 대전 | 36.3504 | 127.3845 |
| 울산 | 35.5384 | 129.3114 |
| 세종 | 36.4800 | 127.2890 |
| 경기 수원 | 37.2636 | 127.0286 |
| 강원 춘천 | 37.8813 | 127.7298 |
| 충북 청주 | 36.6424 | 127.4890 |
| 충남 홍성 | 36.6012 | 126.6608 |
| 전북 전주 | 35.8242 | 127.1480 |
| 전남 무안 | 34.9904 | 126.4817 |
| 경북 안동 | 36.5684 | 128.7294 |
| 경남 창원 | 35.2271 | 128.6811 |
| 제주 제주시 | 33.4996 | 126.5312 |

사용한 Open-Meteo 조회 URL 예시(17개 지점 전체, 365일):

```text
https://archive-api.open-meteo.com/v1/archive?latitude=37.5665,35.1796,35.8714,37.4563,35.1595,36.3504,35.5384,36.48,37.2636,37.8813,36.6424,36.6012,35.8242,34.9904,36.5684,35.2271,33.4996&longitude=126.978,129.0756,128.6014,126.7052,126.8526,127.3845,129.3114,127.289,127.0286,127.7298,127.489,126.6608,127.148,126.4817,128.7294,128.6811,126.5312&start_date=2025-01-01&end_date=2025-12-31&daily=cloud_cover_mean,precipitation_sum,sunshine_duration&models=era5&timezone=Asia%2FSeoul
```

이 조회 결과의 17개 지역 배열에서 매 날짜별 구름량·강수량·일조시간을 각각 평균 내면 저장된 기상 CSV를 재구성할 수 있습니다. **전력시장 지역별 설비용량으로 가중하지 않았으며, 지역 간 발전량 차이를 설명하는 모델은 아닙니다.**

## 저장소 구조

```text
codyssey-M1-1/
├── analysis.py                 # 원본 수집, 품질검사, 기존 시계열 분석
├── insight_extension.py        # 계절·기상 분석 및 SVG 그래프 생성
├── verify.py                   # 임시 폴더 재실행 비교
├── REPORT.md                   # 분석 질문, 결과, 인사이트, 한계, AI 사용 로그
├── README.md
├── requirements.txt
├── data/
│   ├── daily_solar.csv
│   ├── monthly_summary.csv
│   ├── daily_weather_2025.csv  # ERA5 17지점 평균 365일 (입력)
│   ├── seasonal_summary.csv
│   ├── cloud_summary.csv
│   ├── results.json
│   ├── validation.json
│   └── reproducibility.json
└── images/
    ├── 01_trend.png
    ├── 02_monthly.png
    ├── 03_variability.png
    ├── 04_seasons.svg
    └── 05_cloud_weather.svg
```

실행 후 `data/kpx_original.csv`, `data/hourly_solar.csv`도 생성됩니다. 원본 CSV는 `.gitignore`로 제외합니다.

## 해석할 때 주의할 점
- **계절별 최고는 여름, 월별 최고는 4월**입니다. 서로 비교 단위가 다릅니다.
- 구름량 **35% 이하 / 35~65% / 65% 이상**은 이번 분석에 선택한 기준입니다. 기상청 공식 맑음/흐림 분류가 아닙니다.
- 구름량과 발전량의 상관관계는 인과관계가 아닙니다. 1년치 자료만으로 모든 연도에 일반화하지 않습니다.
