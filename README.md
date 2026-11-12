# hyero-congestion-records

혼잡도 예측 순방향 검증의 원자료 백업. 코드와 모델은 팀 저장소
(`hyero-ev-charging-app`, 브랜치 `feature/congestion-prediction`, `congestion/` 폴더)에 있다.

| 경로 | 내용 |
|---|---|
| `forecast_log.db.gz` | 순방향 검증 기록 (SQLite를 gzip으로 압축). 예측 시각, 도착 시각, 예측 등급/점수, 실제 점유율/등급 |
| `logs/` | 매시간 예측 주기 로그, 3일 재학습 로그와 리포트 |
| `reports/` | 검증 리포트 (`report_*.md`) |
| `backup_records.py`, `run_backup.bat` | 원본을 여기로 복사하고 올리는 스크립트 (원본 PC에서만 실행, 매일 23:40 자동) |

## 이 저장소는 이력을 남기지 않는다

올릴 때마다 커밋 하나로 교체한다(강제 푸시). 기록 파일은 계속 누적되는 구조라 최신본에 과거 기록이 전부 들어 있다.
그래서 다른 PC에서는 `git pull`이 아니라 아래 명령으로 최신본에 맞춘다.

## 다른 PC에서 쓰는 법

읽기 전용으로 쓴다. 여기서 파일을 고쳐 올리면 원본 PC의 다음 백업에 덮어써진다.

처음 한 번:

```bash
git clone https://github.com/bhg0211/hyero-congestion-records.git
```

그 뒤 최신본 받기 (저장소 폴더 안에서):

```bash
git fetch origin
git reset --hard origin/main
```

압축 풀기 (같은 폴더에 `forecast_log.db`가 생긴다):

```bash
python -c "import gzip, shutil; shutil.copyfileobj(gzip.open('forecast_log.db.gz'), open('forecast_log.db', 'wb'))"
```

팀 저장소 폴더에서 최신 코드를 받는다.

```bash
git pull origin feature/congestion-prediction
```

팀 저장소의 `congestion/` 폴더에서 리포트를 만든다. `--db` 뒤에 풀린 파일의 경로를 적는다.
결과는 `congestion/` 폴더에 `report_*_YYYYMMDD.md`로 저장된다.

```bash
python report_forward_validation.py --db 경로/forecast_log.db
python report_validation_review.py --db 경로/forecast_log.db
```

- `report_forward_validation.py`: 지역별 평가 건수, 전체/리드타임별 등급 일치율, "항상 여유" 기준, 예측 등급별 일치율
- `report_validation_review.py`: 시간 관계, 혼동행렬, '혼잡' 재현율/정밀도, 점유율 오차, 모델/코드 버전, 빈 구간,
  비교 기준과의 순방향 비교, 충전기 단위 AUC/Brier/확률 보정
- 둘 다 Python 기본 기능과 `python-dotenv`만 쓴다 (scikit-learn 불필요). `report_validation_review.py`의 3번 섹션만
  Supabase 접속(`.env`, `psycopg2`)이 필요하고, 없으면 그 섹션만 "확인 불가"로 나온다.

과거 데이터 평가(경계 표본 제외 전후 AUC, 충전기 단위 Brier score)는 `reports/report_validation_YYYYMMDD_지역.md`에
결과가 있다. 다시 돌리려면 `evaluate_for_report.py`가 필요하고 scikit-learn과 Supabase 접속이 있어야 한다.

## 기록 항목

2026-10-11 17:23 주기부터 예측마다 신뢰도, 반올림 전 점수, 모델 파일 sha, 코드 버전, 예측 시점 점유율,
요일·시간대 평균, 충전기별 확률/실제 상태를 남긴다. 그 전 기록은 이 항목이 비어 있다(NULL).
`runs` 테이블에는 주기별 실행 기록이 있다. 자세한 열 설명은 팀 저장소 `log_predictions.py`의 `EXTRA_COLUMNS`.

## 자동으로 올라오는 것

원본 PC가 켜져 있고 로그인된 상태면 매일 23:40에 최신 기록이 올라온다. PC가 꺼져 있던 날은 올라오지 않고,
다음 백업에 그동안의 기록이 한꺼번에 들어온다 (예측 자체가 멈춘 시간의 기록만 빈다).

## 기록이 비는 구간

원본 PC가 꺼져 있거나 실행이 막힌 시간에는 예측이 없다. `logs/forecast_cycle.log`에 주기별 실행 결과가 남는다.

- 2026-10-10 22:29 ~ 2026-10-11 16:25: PC 절전 및 Windows 스마트 앱 컨트롤 차단으로 실행 안 됨
