import redis
import re
import os
import json
import hashlib
import logging

redis_conn = redis.Redis(host=os.getenv("REDIS_HOST", "localhost"), port=6379, db=0)

def publish_entry_once(data):
    """
    Publish to Redis only if this fingerprint has not been published yet.
    """
    fingerprint = data.get("fingerprint")
    if not fingerprint:
        logging.warning("No fingerprint in data — cannot deduplicate")
        return

    redis_key = f"published:{fingerprint}"

    if redis_conn.set(redis_key, "1", nx=True, ex=3600):
        redis_conn.publish("ledger_updates", json.dumps(data))
        logging.info(f"Published new ledger update for {fingerprint[:8]}")
    else:
        logging.info(f"Skipped duplicate publish for {fingerprint[:8]}")

def normalize_text(text):
    """
    Normalize the input text by stripping whitespace and converting to lowercase.

    Args:
        text (str): The input text to normalize.
    Returns:
        str: The normalized text, stripped of leading/trailing whitespace and converted to lowercase.
    """
    return re.sub(r"\s+", " ", text.strip().lower())

class RedisLogHandler(logging.Handler):
    def emit(self, record):
        log_entry = self.format(record)
        redis_conn.publish("log_stream", json.dumps({"log": log_entry}))