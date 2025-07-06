import redis
import re
import os
import json
import hashlib
import logging

redis_conn = redis.Redis(host=os.getenv("REDIS_HOST", "localhost"), port=6379, db=0)

def publish_entry(data):
    """
    Publish a new entry to the Redis channel.

    Args:
        data (dict): A dictionary containing the entry details. Must include:
            - text (str): Description of the transaction.
            - date (str): Date of the transaction in YYYY-MM-DD format.
            - amount (float): Amount of the transaction.
            - currency (str): Currency of the transaction (e.g., USD, SGD).
            - vendor (str): Name of the vendor or party involved in the transaction.
            - ttype (str): Type of transaction, either "Debit" or "Credit".
            - referenceid (str): Unique reference ID for the transaction.
            - label (str): Category of the transaction (e.g., Meals & Entertainment, Transport).
    """
    redis_conn.publish("ledger_updates", json.dumps(data))

def normalize_text(text):
    """
    Normalize the input text by stripping whitespace and converting to lowercase.

    Args:
        text (str): The input text to normalize.
    Returns:
        str: The normalized text, stripped of leading/trailing whitespace and converted to lowercase.
    """
    return re.sub(r"\s+", " ", text.strip().lower())

def compute_fingerprint(text):
    """
    Compute a SHA-256 fingerprint for the given text.

    Args:
        text (str): The input text to compute the fingerprint for.
    Returns:
        str: The SHA-256 hash of the normalized text, represented as a hexadecimal string.
    """
    norm_body = normalize_text(text)
    combined = (norm_body).encode("utf-8")
    return hashlib.sha256(combined).hexdigest()

class RedisLogHandler(logging.Handler):
    def emit(self, record):
        log_entry = self.format(record)
        redis_conn.publish("log_stream", json.dumps({"log": log_entry}))