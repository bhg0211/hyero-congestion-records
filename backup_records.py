"""혼잡도 순방향 검증 기록을 이 저장소로 복사하고 커밋/푸시한다.

원본(hyero-ev-charging-app/congestion)은 읽기만 한다. forecast_log.db는 스케줄러가 쓰는 중일 수 있어서
파일 복사가 아니라 SQLite 백업 API로 일관된 사본을 뜬다. 코드와 모델은 팀 저장소에 있으므로 여기 넣지 않는다.

- 기록 파일은 gzip으로 압축한 forecast_log.db.gz만 올린다 (GitHub 파일당 100MB 제한 때문).
- 올릴 때마다 이력을 새 커밋 하나로 교체하고 강제 푸시한다. 기록 파일은 누적되는 구조라 최신본에 과거가
  다 들어 있어서 예전 사본을 이력에 쌓아 둘 이유가 없고, 쌓으면 저장소가 하루 수십 MB씩 커진다.
- 대신 이 PC의 LOCAL_COPIES 폴더에 날짜별 사본을 KEEP_DAYS일치 남긴다.

사용: python backup_records.py            (복사 + 커밋 + 강제 푸시)
      python backup_records.py --no-push  (복사 + 커밋까지만)
"""
import argparse
import glob
import gzip
import os
import shutil
import sqlite3
import subprocess
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.join(os.path.dirname(HERE), "hyero-ev-charging-app", "congestion")
LOCAL_COPIES = os.path.join(os.path.dirname(HERE), "forecast_log_backups")
KEEP_DAYS = 7
GIT_ID = ["-c", "user.name=배혜관", "-c", "user.email=gorhks0211@gmail.com"]

# (원본 패턴, 이 저장소 안 폴더)
TEXT_FILES = [
    ("forecast_cycle.log", "logs"),
    ("retrain_status.log", "logs"),
    ("retrain_run.log", "logs"),
    ("retrain_report_*.txt", "logs"),
    ("report_*.md", "reports"),
]


def backup_db():
    """일관된 사본을 떠서 검사하고 압축한다. (예측 건수, 마지막 예측 시각, 압축 파일 MB)"""
    src_path = os.path.join(SOURCE, "forecast_log.db")
    tmp_path = os.path.join(HERE, "forecast_log.db")   # .gitignore 대상, 압축 뒤 지움
    gz_path = os.path.join(HERE, "forecast_log.db.gz")
    if os.path.exists(tmp_path):
        os.remove(tmp_path)
    src = sqlite3.connect(f"file:{src_path}?mode=ro", uri=True, timeout=120)
    dst = sqlite3.connect(tmp_path)
    try:
        src.backup(dst)
        check = dst.execute("PRAGMA integrity_check").fetchone()[0]
        if check != "ok":
            raise RuntimeError(f"사본 무결성 검사 실패: {check}")
        n_rows, last_predicted = dst.execute("SELECT count(*), max(predicted_at) FROM predictions").fetchone()
    finally:
        src.close()
        dst.close()
    with open(tmp_path, "rb") as f_in, gzip.open(gz_path + ".tmp", "wb", compresslevel=6) as f_out:
        shutil.copyfileobj(f_in, f_out)
    os.replace(gz_path + ".tmp", gz_path)
    os.remove(tmp_path)
    return n_rows, last_predicted, os.path.getsize(gz_path) / 1024 / 1024


def keep_local_copy():
    """압축본을 날짜별로 남기고 KEEP_DAYS일 지난 것은 지운다."""
    os.makedirs(LOCAL_COPIES, exist_ok=True)
    shutil.copy2(os.path.join(HERE, "forecast_log.db.gz"),
                 os.path.join(LOCAL_COPIES, f"forecast_log_{datetime.now():%Y%m%d}.db.gz"))
    cutoff = datetime.now() - timedelta(days=KEEP_DAYS)
    for path in glob.glob(os.path.join(LOCAL_COPIES, "forecast_log_*.db.gz")):
        if datetime.fromtimestamp(os.path.getmtime(path)) < cutoff:
            os.remove(path)


def copy_text_files():
    copied = 0
    for pattern, folder in TEXT_FILES:
        os.makedirs(os.path.join(HERE, folder), exist_ok=True)
        for path in glob.glob(os.path.join(SOURCE, pattern)):
            shutil.copy2(path, os.path.join(HERE, folder, os.path.basename(path)))
            copied += 1
    return copied


def git(*args, check=True):
    return subprocess.run(["git", "-C", HERE, *args], check=check, capture_output=True, text=True, encoding="utf-8")


def commit_as_single_snapshot(message):
    """이력을 지금 상태 하나짜리 커밋으로 교체한다 (이 저장소의 main만)."""
    git("checkout", "--orphan", "_snapshot")
    git("add", "-A")
    git(*GIT_ID, "commit", "-m", message)
    git("branch", "-D", "main", check=False)
    git("branch", "-m", "main")
    git("reflog", "expire", "--expire=now", "--all", check=False)
    git("gc", "--prune=now", "--quiet", check=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-push", action="store_true")
    args = parser.parse_args()

    n_rows, last_predicted, gz_mb = backup_db()
    keep_local_copy()
    n_files = copy_text_files()
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] 기록 사본: 예측 {n_rows:,}건 (마지막 예측 {last_predicted}), "
          f"압축본 {gz_mb:.1f}MB, 로그/리포트 {n_files}개")

    message = f"기록 백업 {datetime.now():%Y-%m-%d %H:%M} (예측 {n_rows:,}건, 마지막 {last_predicted})"
    commit_as_single_snapshot(message)
    print(f"커밋: {message}")
    if not args.no_push:
        result = git("push", "--force", "-u", "origin", "main", check=False)
        print("푸시 완료" if result.returncode == 0 else f"푸시 실패:\n{result.stderr}")
        raise SystemExit(result.returncode)
