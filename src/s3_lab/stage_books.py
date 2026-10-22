#!/usr/bin/env python3
"""Download books from Project Gutenberg and stage them in a public S3 bucket."""
import json
import logging
import os
import sys
import time

import boto3
import requests
from botocore.exceptions import ClientError

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

s3 = boto3.client("s3", region_name="us-east-1")


def parse_args():
    """Return (list_file, index_path, bucket) from the command line."""
    if len(sys.argv) < 4:
        log.error("Usage: stage_books.py BOOK_LIST INDEX_HTML BUCKET")
        sys.exit(1)
    return sys.argv[1], sys.argv[2], sys.argv[3]


def download_books(list_file, dest_dir):
    """Download each URL in list_file into dest_dir; return the local paths."""
    os.makedirs(dest_dir, exist_ok=True)
    paths = []
    with open(list_file) as f:
        urls = [line.strip() for line in f if line.strip()]
    for url in urls:
        path = os.path.join(dest_dir, url.split("/")[-1])
        if os.path.exists(path):
            log.info(f"Already downloaded, skipping: {path}")
            paths.append(path)
            continue
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            with open(path, "wb") as out:
                out.write(response.content)
            paths.append(path)
            log.info(f"Downloaded {url} -> {path}")
        except requests.RequestException as e:
            log.error(f"Error downloading {url}: {e}")
        time.sleep(1)
    return paths


def create_bucket(bucket):
    """Check if bucket exists, create it if it doesn't, return True if it exists afterwards."""
    try:
        s3.head_bucket(Bucket=bucket)
        log.info(f"Bucket {bucket} already exists")
        return True
    except ClientError:
        pass
    try:
        s3.create_bucket(Bucket=bucket)
        log.info(f"Created bucket: {bucket}")
        return True
    except ClientError as e:
        log.error(f"Error creating bucket {bucket}: {e}")
        return False


def make_public(bucket):
    """Turn off Block Public Access and attach a public-read bucket policy."""
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": "*",
                "Action": "s3:GetObject",
                "Resource": f"arn:aws:s3:::{bucket}/*",
            }
        ],
    }
    try:
        s3.put_public_access_block(
            Bucket=bucket,
            PublicAccessBlockConfiguration={
                "BlockPublicAcls": False,
                "IgnorePublicAcls": False,
                "BlockPublicPolicy": False,
                "RestrictPublicBuckets": False,
            },
        )
        s3.put_bucket_policy(Bucket=bucket, Policy=json.dumps(policy))
        log.info(f"Bucket {bucket} is now public")
        return True
    except ClientError as e:
        log.error(f"Error making bucket {bucket} public: {e}")
        return False


def upload_files(bucket, file_paths):
    """Upload each file to the bucket's top level; return the success count."""
    count = 0
    for path in file_paths:
        key = os.path.basename(path)
        try:
            with open(path, "rb") as f:
                s3.put_object(
                    Bucket=bucket,
                    Key=key,
                    Body=f,
                    ContentType="text/plain; charset=utf-8",
                )
            count += 1
            log.info(f"Uploaded {path} to s3://{bucket}/{key}")
        except ClientError as e:
            log.error(f"Error uploading {path}: {e}")
    log.info(f"Uploaded {count} of {len(file_paths)} books")
    return count


def upload_index(bucket, index_path):
    """Upload index.html as a web page; return True on success."""
    try:
        with open(index_path, "rb") as f:
            s3.put_object(
                Bucket=bucket,
                Key="index.html",
                Body=f,
                ContentType="text/html",
            )
        log.info(f"Uploaded {index_path} to s3://{bucket}/index.html")
        return True
    except FileNotFoundError:
        log.error(f"Local file not found: {index_path}")
        return False
    except ClientError as e:
        log.error(f"Error uploading index page: {e}")
        return False


def main():
    list_file, index_path, bucket = parse_args()
    paths = download_books(list_file, "books")
    if not paths:
        log.error("No books downloaded")
        sys.exit(1)
    if not create_bucket(bucket) or not make_public(bucket):
        sys.exit(1)
    count = upload_files(bucket, paths)
    ok = upload_index(bucket, index_path)
    url = f"https://{bucket}.s3.amazonaws.com/index.html"
    if ok and count == len(paths):
        log.info(f"Success: {count} books and index.html uploaded. View at {url}")
    else:
        log.error(f"Finished with errors: {count}/{len(paths)} books, index uploaded: {ok}")
        log.info(f"Index page (if uploaded): {url}")


if __name__ == "__main__":
    main()