#!/bin/bash

# 定期的にscreenshotsフォルダの変更をチェックし、変更があればGitHubにプッシュするスクリプト
# 使用方法: ./push_to_github.sh

INTERVAL=300 # 5分ごとにチェック (スクレイパーの間隔に合わせる)

echo "=== GitHub自動プッシュ監視を開始します ==="
echo "監視対象: screenshots/ (間隔: ${INTERVAL}秒)"

while true; do
  # 変更があるか確認
  if [[ -n $(git status -s screenshots/) ]]; then
    timestamp=$(date "+%Y-%m-%d %H:%M:%S")
    echo "[$timestamp] 変更を検知しました。プッシュを実行します..."
    
    git add screenshots/
    git commit -m "Update charts: $timestamp"
    git push origin main
    
    if [ $? -eq 0 ]; then
      echo "[$timestamp] プッシュ成功！"
    else
      echo "[$timestamp] プッシュに失敗しました。ネットワーク接続やリポジトリ設定を確認してください。"
    fi
  else
    echo "[$(date "+%H:%M:%S")] 変更なし。待機中..."
  fi
  
  sleep $INTERVAL
done
