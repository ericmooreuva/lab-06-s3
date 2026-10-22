#!/usr/bin/env python3

import json
import logging
import os
import sys
import time

import boto3
import requests
from botocore.exceptions import ClientError

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

s3 = boto3.client("s3", region_name="us-east-1")


def parse_args():
    if len(sys.argv) < 4:
        log.error("Usage: stage_books.py book_urls.txt index.html bucket-name")
        sys.exit(1)
    list_file = sys.argv[1]
    index_path = sys.argv[2]
    bucket = sys.argv[3]
    return list_file, index_path, bucket


def download_books(list_file, dest_dir):
    os.makedirs(dest_dir, exist_ok=True)
    paths = []

    with open(list_file) as f:
        lines = f.readlines()

    for line in lines:
        url = line.strip()
        if url == "":
            continue

        filename = url.split("/")[-1]
        path = os.path.join(dest_dir, filename)

        if os.path.exists(path):
            log.info(f"Skipping {path}, already downloaded")
            paths.append(path)
            continue

        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            with open(path, "wb") as f:
                f.write(response.content)
            log.info(f"Downloaded {path}")
            paths.append(path)
        except requests.RequestException as e:
            log.error(f"Error downloading {url}: {e}")

        time.sleep(1)

    return paths


def create_bucket(bucket):
    try:
        s3.head_bucket(Bucket=bucket)
        log.info(f"Bucket {bucket} already exists")
        return True
    except ClientError:
        pass

    try:
        s3.create_bucket(Bucket=bucket)
        log.info(f"Created bucket {bucket}")
        return True
    except ClientError as e:
        log.error(f"Error creating bucket: {e}")
        return False


def make_public(bucket):
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
        s3.put_bucket_policy(Bucket=bucket, Policy=json.dumps(policy))
        log.info(f"Bucket {bucket} is now public")
        return True
    except ClientError as e:
        log.error(f"Error making bucket public: {e}")
        return False


def upload_files(bucket, file_paths):
    count = 0
    for path in file_paths:
        key = os.path.basename(path)
        try:
            s3.upload_file(
                path, bucket, key,
                ExtraArgs={"ContentType": "text/plain; charset=utf-8"},
            )
            log.info(f"Uploaded {key}")
            count += 1
        except ClientError as e:
            log.error(f"Error uploading {path}: {e}")
    return count


def upload_index(bucket, index_path):
    try:
        s3.upload_file(
            index_path, bucket, "index.html",
            ExtraArgs={"ContentType": "text/html"},
        )
        log.info("Uploaded index.html")
        return True
    except FileNotFoundError:
        log.error(f"File not found: {index_path}")
        return False
    except ClientError as e:
        log.error(f"Error uploading index.html: {e}")
        return False


def main():
    list_file, index_path, bucket = parse_args()

    file_paths = download_books(list_file, "books")
    if len(file_paths) == 0:
        log.error("No books downloaded")
        sys.exit(1)

    if not create_bucket(bucket):
        sys.exit(1)

    if not make_public(bucket):
        sys.exit(1)

    count = upload_files(bucket, file_paths)
    index_ok = upload_index(bucket, index_path)

    if count == len(file_paths) and index_ok:
        log.info(f"Success! Uploaded {count} books")
    else:
        log.error(f"Some uploads failed. Uploaded {count} books")

    log.info(f"Public page: https://{bucket}.s3.amazonaws.com/index.html")


if __name__ == "__main__":
    main()
