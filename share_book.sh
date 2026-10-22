#!/bin/bash
# Download one book, upload it to a private S3 bucket, and print a presigned URL.
set -euo pipefail

# Validate positional arguments
if [ "$#" -ne 3 ]; then
    echo "Usage: $0 BOOK_URL BUCKET EXPIRES_SECONDS" >&2
    echo "Example: $0 https://www.gutenberg.org/cache/epub/84/pg84.txt secret-mst3k 604800" >&2
    exit 1
fi

BOOK_URL="$1"
BUCKET="$2"
EXPIRES="$3"
FILE_NAME="$(basename "$BOOK_URL")"
LOCAL_PATH="books/$FILE_NAME"

# Download the book, keeping the file name from the URL
mkdir -p books
echo "Downloading $BOOK_URL -> $LOCAL_PATH"
curl -fsSL "$BOOK_URL" -o "$LOCAL_PATH"

# Create the bucket unless it already exists
if aws s3 ls "s3://$BUCKET" > /dev/null 2>&1; then
    echo "Bucket $BUCKET already exists"
else
    echo "Creating bucket $BUCKET"
    aws s3 mb "s3://$BUCKET"
fi

# Upload the book; the bucket and object stay private
aws s3 cp "$LOCAL_PATH" "s3://$BUCKET/$FILE_NAME" \
    --content-type "text/plain; charset=utf-8"

# Presign a URL that expires after EXPIRES seconds
URL="$(aws s3 presign "s3://$BUCKET/$FILE_NAME" --expires-in "$EXPIRES")"
echo "Presigned URL (expires in $EXPIRES seconds):"
echo "$URL"
