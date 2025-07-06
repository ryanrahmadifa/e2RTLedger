import imaplib
import email
from email.header import decode_header
from email.utils import parsedate_to_datetime
import time
import requests
import os
import hashlib
import tempfile
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from fastapi_app.redis_publisher import RedisLogHandler

IMAP_SERVER = "imap.gmail.com"
EMAIL_ACCOUNT = os.getenv("EMAIL_ACCOUNT")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

FASTAPI_CLASSIFY_URL = os.getenv("FASTAPI_CLASSIFY_URL", "http://fastapi:8000/classify/")
FASTAPI_OCR_URL = os.getenv("FASTAPI_OCR_URL", "http://fastapi:8000/ocr_result/")
FASTAPI_OCR_SUBMIT_URL = os.getenv("FASTAPI_OCR_SUBMIT_URL", "http://fastapi:8000/ocr_document/")
FASTAPI_REDIS_CHECK_URL = os.getenv("FASTAPI_REDIS_CHECK_URL", "http://fastapi:8000/redis_check/")

processing_emails = set()
processing_lock = threading.Lock()

def setup_logging():
    formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
    redis_handler = RedisLogHandler()
    redis_handler.setFormatter(formatter)

    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    logger.addHandler(redis_handler)

setup_logging()

def decode_str(s) -> str:
    """
    Decode an email header string.

    Args:
        s (str): The string to decode, typically an email header value.
    Returns:
        str: The decoded string, or an empty string if the input is None or empty.
    """
    if not s:
        return ""
    decoded, enc = decode_header(s)[0]
    return decoded.decode(enc or "utf-8") if isinstance(decoded, bytes) else decoded

def compute_fingerprint(*args) -> str:
    """
    Compute a SHA-256 fingerprint for the given input strings.

    Args:
        *args: Variable length argument list of strings to include in the fingerprint.
    Returns:
        str: The computed SHA-256 fingerprint as a hexadecimal string.
    """
    combined = "".join((a or "").strip() for a in args).encode("utf-8")
    return hashlib.sha256(combined).hexdigest()

def is_already_processing_or_processed(fingerprint: str) -> bool:
    """
    Check if an email is already being processed or has been processed.

    Args:
        fingerprint (str): The SHA-256 fingerprint of the email.
    Returns:
        bool: True if the email is already being processed or has been processed, False otherwise.
    """
    with processing_lock:
        if fingerprint in processing_emails:
            return True
        try:
            resp = requests.post(FASTAPI_REDIS_CHECK_URL, json={"fingerprint": fingerprint})
            if resp.ok and resp.json().get("exists", False):
                return True
        except Exception as e:
            logging.error(f"Redis check failed: {e}")
            return True
        processing_emails.add(fingerprint)
        return False

def remove_processing_mark(fingerprint: str) -> None:
    """
    Remove the processing mark for a given email fingerprint.
    """
    with processing_lock:
        processing_emails.discard(fingerprint)

def extract_attachments(msg: email.message.EmailMessage) -> list[dict]:
    """
    Extract attachments from an email message.

    Args:
        msg (email.message.EmailMessage): The email message object.
    Returns:
        list: A list of dictionaries containing attachment filenames and their content.
    """
    attachments = []
    for part in msg.walk():
        if part.get_content_maintype() == "multipart":
            continue
        if "attachment" in str(part.get("Content-Disposition", "")).lower():
            filename = decode_str(part.get_filename())
            content = part.get_payload(decode=True)
            if filename and content:
                attachments.append({"filename": filename, "content": content})
    logging.debug(f"Extracted {len(attachments)} attachments.")
    return attachments

def submit_ocr(attachment: dict) -> str:
    """
    Submit an attachment for OCR processing.
    This function uploads the attachment to a FastAPI endpoint for OCR processing,
    waits for the result for 60 seconds, and returns the OCR text.

    Args:
        attachment (dict): A dictionary containing the attachment filename and content.
    Returns:
        str: The OCR result text if successful, or an empty string if failed.
    """
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(attachment["filename"])[1]) as tmpf:
            tmpf.write(attachment["content"])
            tmpf.flush()
        with open(tmpf.name, "rb") as f:
            files = {"file": (attachment["filename"], f)}
            submit_resp = requests.post(FASTAPI_OCR_SUBMIT_URL, files=files)
        os.unlink(tmpf.name)

        if not submit_resp.ok:
            logging.warning(f"OCR submission failed for {attachment['filename']}: {submit_resp.text}")
            return ""

        task_id = submit_resp.json().get("task_id")
        logging.info(f"OCR task submitted for {attachment['filename']} (Task ID: {task_id})")

        for _ in range(60):
            result_resp = requests.get(f"{FASTAPI_OCR_URL}{task_id}")
            if result_resp.ok:
                status = result_resp.json().get("status")
                if status == "completed":
                    return result_resp.json().get("text", "")
                elif status == "failed":
                    logging.warning(f"OCR failed for {attachment['filename']}")
                    return ""
            time.sleep(1)
        logging.warning(f"OCR timed out for {attachment['filename']}")
        return ""

    except Exception as e:
        logging.error(f"OCR processing error for {attachment['filename']}: {e}")
        return ""

def get_email_body(msg: email.message.EmailMessage) -> str:
    """
    Extract the body text from an email message.

    Args:
        msg (email.message.EmailMessage): The email message object.
    Returns:
        str: The plain text body of the email, or an empty string if not found.
    """
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain" and "attachment" not in str(part.get("Content-Disposition", "")):
                try:
                    return part.get_payload(decode=True).decode()
                except Exception:
                    continue
    else:
        try:
            return msg.get_payload(decode=True).decode()
        except Exception:
            pass
    return ""

def fetch_emails() -> list[dict]:
    """
    Fetch emails from the IMAP server.
    This function connects to the IMAP server, searches for emails from a specific sender,
    and processes each email to extract relevant information such as subject, date, body,
    attachments, and computes a fingerprint for each email.

    Returns:
        list: A list of dictionaries containing email data including subject, date, body,
                attachments, and fingerprint.
    """
    logging.info("Connecting to IMAP...")
    mail = imaplib.IMAP4_SSL(IMAP_SERVER)
    mail.login(EMAIL_ACCOUNT, EMAIL_PASSWORD)
    mail.select("inbox")
    result, data = mail.search(None, 'FROM', 'finops@earlybirdapp.co')
    email_ids = data[0].split()
    logging.debug(f"Found {len(email_ids)} emails from finops@earlybirdapp.co")

    emails = []
    for e_id in email_ids:
        try:
            _, msg_data = mail.fetch(e_id, "(RFC822)")
            msg = email.message_from_bytes(msg_data[0][1])

            subject = decode_str(msg.get("Subject", ""))
            raw_date = msg.get("Date", "")
            date_str = parsedate_to_datetime(raw_date).strftime("%Y-%m-%d") if raw_date else time.strftime("%Y-%m-%d")
            body = get_email_body(msg)

            fingerprint = compute_fingerprint(subject, body)
            if is_already_processing_or_processed(fingerprint):
                logging.info(f"Skipping already processed/processing email: {subject} ({fingerprint[:8]}...)")
                continue

            attachments = extract_attachments(msg)
            emails.append({
                "subject": subject,
                "date": date_str,
                "body": body,
                "attachments": attachments,
                "fingerprint": fingerprint
            })
        except Exception as e:
            logging.error(f"Error fetching email {e_id}: {e}")
    mail.logout()
    logging.info("IMAP disconnected.")
    return emails

def process_email(email_data: dict) -> None:
    """
    Process the email data by performing OCR on attachments and classifying the email content.
    This function extracts the subject, body, and attachments from the email,
    submits attachments for OCR processing, combines the results with the email body,
    and sends the combined text to a FastAPI endpoint for classification.

    Args:
        email_data (dict): A dictionary containing email data including subject, date, body,
                           attachments, and fingerprint.
    """
    fingerprint = email_data["fingerprint"]
    try:
        ocr_texts = []
        if email_data["attachments"]:
            with ThreadPoolExecutor(max_workers=3) as exec_:
                futures = [exec_.submit(submit_ocr, att) for att in email_data["attachments"]]
                for f in as_completed(futures):
                    text = f.result()
                    if text:
                        ocr_texts.append(text)

        combined_text = f"{email_data['subject']}\n{email_data['body']}\n\nAttachments OCR:\n" + "\n\n".join(ocr_texts)

        resp = requests.post(FASTAPI_CLASSIFY_URL, json={
            "text": combined_text,
            "date": email_data["date"],
            "fingerprint": fingerprint,
        })
        if resp.ok:
            logging.info(f"Classification success: {resp.json()}")
        else:
            logging.error(f"Classification failed: {resp.text}")
    except Exception as e:
        logging.exception(f"Failed processing email {fingerprint[:8]}...")
    finally:
        remove_processing_mark(fingerprint)

def main_loop() -> None:
    """
    Main loop for fetching and processing emails.
    This function continuously checks for new emails every 10 seconds,
    fetches them, and processes each email using a thread pool to handle OCR and classification concurrently.
    Maximum number of concurrent threads is set to 5.
    """
    with ThreadPoolExecutor(max_workers=5) as executor:
        while True:
            try:
                new_emails = fetch_emails()
                if new_emails:
                    logging.info(f"Processing {len(new_emails)} new emails")
                    for email_data in new_emails:
                        executor.submit(process_email, email_data)
                else:
                    logging.debug("No new emails found")
            except Exception:
                logging.exception("Unhandled error in main loop")
            time.sleep(10)

if __name__ == "__main__":
    main_loop()
