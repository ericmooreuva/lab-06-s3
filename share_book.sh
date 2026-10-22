#!/bin/bash
set -euo pipefail

if [ "$#" -lt 3 ]; then
    echo "Usage: $0 BOOK_URL BUCKET SECONDS"
    exit 1
fi

URL="$1"
BUCKET="$2"
SECONDS_VALID="$3"
FILE="$(basename "$URL")"

mkdir -p books
curl -o "books/$FILE" "$URL"

if ! aws s3 ls "s3://$BUCKET" > /dev/null 2>&1; then
    aws s3 mb "s3://$BUCKET"
fi

aws s3 cp "books/$FILE" "s3://$BUCKET/$FILE" --content-type "text/plain; charset=utf-8"

aws s3 presign "s3://$BUCKET/$FILE" --expires-in "$SECONDS_VALID"
