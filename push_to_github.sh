#!/bin/bash

# 定期的にscreenshotsフォルダの変更をチェックし、変更があればGitHubにプッシュするスクリプト
# 使用方法: ./push_to_github.sh


INTERVAL=300 # 5分ごとにチェック

echo "=== GitHub自動プッシュ監視を開始します ==="
echo "監視条件: 平日 09:00〜15:30 (祝日除く)"
echo "監視対象: screenshots/ (間隔: ${INTERVAL}秒)"

while true; do
  # Pythonを使って現在時刻が営業時間内かチェック (Exit code 0: YES, 1: NO)
  python3 -c "
import jpholiday, datetime
now = datetime.datetime.now()
is_weekend = now.weekday() >= 5
is_holiday = jpholiday.is_holiday(now.date())
t = now.time()
is_morning = datetime.time(9, 0) <= t <= datetime.time(11, 30)
is_afternoon = datetime.time(12, 30) <= t <= datetime.time(15, 30)
is_time_ok = is_morning or is_afternoon

if not is_weekend and not is_holiday and is_time_ok:
    exit(0)
else:
    print(f'営業時間外です (週末:{is_weekend}, 祝日:{is_holiday}, 時間:{now.strftime(\"%H:%M\")})')
    exit(1)
"

  # 営業時間内(exit 0)の場合のみ処理
  if [ $? -eq 0 ]; then
    if [[ -n $(git status -s) ]]; then
        timestamp=$(date "+%Y-%m-%d %H:%M:%S")
        echo "[$timestamp] 変更を検知しました。プッシュを実行します..."
        
        git add .
        git commit -m "Update charts: $timestamp"
        git push origin main
        
        if [ $? -eq 0 ]; then
          echo "[$timestamp] プッシュ成功！"
        else
          echo "[$timestamp] プッシュに失敗しました。ネットワーク接続を確認してください。"
        fi
    else
        echo "[$(date "+%H:%M:%S")] 変更なし。待機中..."
    fi
  else
    # 営業時間外
    echo "[$(date "+%H:%M:%S")] 営業時間外のため待機中..."
  fi
  
  sleep $INTERVAL
done
