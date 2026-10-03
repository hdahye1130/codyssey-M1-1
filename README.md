# 한국 태양광 발전량 시계열 분석

KPX 전력시장 참여 태양광 발전기의 2025년 전력거래량을 분석합니다. 한국 전체 태양광 총생산량은 아니며, ESS 충·방전이 포함됩니다.

## 결과 보기
`REPORT.md`가 제출용 보고서입니다. `images/`에 그래프 3개, `data/results.json`에 핵심 수치와 품질 검사 결과, `data/validation.json`에 자동 검증 결과가 있습니다.

## 실행 방법
Python 3.11 또는 3.12를 권장합니다. 저장소 폴더에서 터미널을 열고 아래 명령을 순서대로 실행합니다. Windows에서는 `python3` 대신 `python`을 사용할 수 있습니다.

```bash
python3 -m pip install -r requirements.txt
python3 analysis.py
python3 verify.py
```

GitHub 저장소에는 용량을 줄이기 위해 6MB 이상의 원본 CSV를 넣지 않았습니다. `analysis.py`는 `data/kpx_original.csv`가 없으면 한국전력거래소(KPX)의 공식 공공데이터 파일을 자동으로 내려받고, 파생 CSV·그래프·보고서·검증 JSON을 다시 생성합니다. 계정이나 API 키는 필요하지 않습니다.

## 데이터 출처
- 공식 페이지: https://www.data.go.kr/data/15065269/fileData.do
- 파일명: 한국전력거래소_지역별 시간별 태양광 및 풍력 발전량_20251231
- 제공기관: 한국전력거래소(KPX)
- 수집일: 2026-10-03
- 분석 기간: 2025-01-01~2025-12-31
- 원본: 166,440행, CP949 인코딩
- 태양광 사용 행: 148,920행(17지역 × 365일 × 24시간)
- 실제 컬럼: 거래일, 거래시간, 지역, 연료원, 전력거래량(MWh)

필요하면 아래 명령으로 공식 원본을 다시 내려받아 검증할 수 있습니다.

```bash
python3 analysis.py --download
```

코드는 공식 파일의 컬럼과 행 수가 예상과 다르면 기존 원본을 자동으로 교체하지 않고 오류를 내도록 작성되어 있습니다.

## 저장소 구조

```text
codyssey-M1-1/
├── analysis.py
├── verify.py
├── REPORT.md
├── README.md
├── requirements.txt
├── data/
│   ├── daily_solar.csv
│   ├── monthly_summary.csv
│   ├── results.json
│   ├── validation.json
│   └── reproducibility.json
└── images/
    ├── 01_trend.png
    ├── 02_monthly.png
    └── 03_variability.png
```

실행 후에는 `data/kpx_original.csv`와 `data/hourly_solar.csv`도 생성됩니다. 원본 CSV는 `.gitignore`에 포함되어 GitHub에 다시 올라가지 않도록 했습니다.

월별 비교는 월별 총합이 아니라 **평균 일발전량**을 사용해 월의 일수 차이를 줄였습니다. 7일/30일 이동평균과 7일 표준편차는 완전한 계산 창에만 값을 만들기 때문에 시작 부분이 비어 있는 것이 정상입니다. PNG의 제목과 축은 운영체제별 한글 폰트 문제를 피하기 위해 영어로 표기하고, 보고서에서 한국어로 설명합니다.
