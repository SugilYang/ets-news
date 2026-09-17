#!/usr/bin/env bash
# 오늘 후보 파일이 없을 때 GitHub Actions 수집을 즉시 1회 실행시킨다(db/.kick 을 갱신해 푸시 → daily.yml push 트리거).
set -e
cd "$(dirname "$0")/.."
TODAY=$(TZ=Asia/Seoul date +%F)
if [ -f "db/candidates-$TODAY.json" ]; then echo "후보 있음: $TODAY"; exit 0; fi
mkdir -p db
echo "kick $(TZ=Asia/Seoul date '+%F %T KST')" > db/.kick
git add db/.kick
git -c user.name="ETS News Bot" -c user.email="actions@users.noreply.github.com" commit -q -m "수집 강제 실행: $TODAY"
git push -q origin main
echo "수집 트리거 푸시 완료 ($TODAY)"
