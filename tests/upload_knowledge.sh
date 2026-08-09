#!/bin/bash
# 批量上传学校资料到知识库（admin uid=1）
# 按一级目录名作为 category；跳过 ._ 开头文件
API="http://localhost:8000/api/knowledge/add"
ROOT="/tmp/school"
LOG=/tmp/knowledge_upload.log
: > $LOG

echo "start $(date)" >> $LOG
OK=0; SKIP=0; FAIL=0; EMPTY=0

find "$ROOT" -type f \( -name "*.pdf" -o -name "*.docx" \) ! -name "._*" | sort | while read -r f; do
  rel="${f#$ROOT/}"
  # 一级目录 = 学校相关资料 下的第一层（去掉根目录名）
  cat_dir=$(echo "$rel" | cut -d'/' -f2)
  [ -z "$cat_dir" ] && cat_dir="inbox"
  fname=$(basename "$f")

  resp=$(curl -s -X POST "$API" \
    -H "X-User-Id: 1" -H "X-Username: admin" \
    -F "file=@$f" \
    -F "category=$cat_dir" 2>&1)
  if echo "$resp" | grep -q '"success":true'; then
    chunks=$(echo "$resp" | grep -o '"chunks":[0-9]*' | cut -d: -f2)
    if [ "$chunks" = "0" ]; then
      echo "EMPTY  cat=$cat_dir file=$fname (扫描件/无文本)" | tee -a $LOG
      EMPTY=$((EMPTY+1))
    else
      echo "OK     cat=$cat_dir chunks=$chunks file=$fname" | tee -a $LOG
      OK=$((OK+1))
    fi
  else
    echo "FAIL   cat=$cat_dir file=$fname resp=$resp" | tee -a $LOG
    FAIL=$((FAIL+1))
  fi
done
echo "done $(date) OK=$OK SKIP=$SKIP EMPTY=$EMPTY FAIL=$FAIL" | tee -a $LOG
