from fastapi import FastAPI, HTTPException, File, UploadFile, BackgroundTasks
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware
from .nlp import classify_email
from .db import save_entry
from .redis_publisher import *
import traceback
import uuid
from contextlib import asynccontextmanager
ocr_results = {}

REDIS_PROCESSED_SET = "processed_fingerprints"

class EmailText(BaseModel):
    text: str = Field(..., min_length=1)
    date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="Date in YYYY-MM-DD format")
    fingerprint: str = Field(..., description="Fingerprint for deduplication")

class FingerprintCheck(BaseModel):
    fingerprint: str = Field(..., description="Fingerprint to check")

class ClassifiedResult(BaseModel):
    """
    Represents the result of classifying an email.
    """
    text: str = Field(..., min_length=1, description="Short description of the transaction")
    date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="Date of the transaction in YYYY-MM-DD format")
    amount: float = Field(..., ge=0, description="Amount of the transaction")
    currency: str = Field(..., min_length=3, max_length=4, description="Currency of the transaction (e.g., USD, SGD)")
    vendor: str = Field(..., min_length=1, description="Name of the merchant or party involved in the transaction")
    ttype: str = Field(..., description="Type of the transaction")
    referenceid: str = Field(..., description="Reference ID for the transaction")
    label: str = Field(..., description="Label for the transaction")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup and shutdown events for the FastAPI application.
    """
    redis_conn.delete(REDIS_PROCESSED_SET)
    logger = logging.getLogger(__name__)
    handler = RedisLogHandler()
    formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    for name in ["uvicorn", "email_listener", "uvicorn.access", "uvicorn.error"]:
        logger = logging.getLogger(name)
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

    yield

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def perform_ocr(file_bytes: bytes, filename: str) -> str:
    """
    Function to perform OCR on a document or image file.
    Uses PyMuPDF (fitz) to extract text from PDF or image files.
    Supports both PDF and common image formats (PNG, JPG, JPEG).

    Args:
        file_bytes (bytes): The content of the file to process.
        filename (str): The name of the file, used to determine its type.
    Returns:
        str: The extracted text from the document or image.
    """
    import os
    import tempfile
    import fitz

    supported_images = [".png", ".jpg", ".jpeg"]
    supported_pdfs = [".pdf"]

    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(filename)[1]) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name

    try:
        full_text = ""

        if any(filename.endswith(ext) for ext in supported_pdfs):
            doc = fitz.open(tmp_path)
            for page_num, page in enumerate(doc):
                text = page.get_text().strip()
                if not text:
                    matrix = fitz.Matrix(2, 2)
                    pix = page.get_pixmap(matrix=matrix)

                    ocr_doc = fitz.open()
                    ocr_page = ocr_doc.new_page(width=pix.width, height=pix.height)
                    ocr_page.insert_image(fitz.Rect(0, 0, pix.width, pix.height), pixmap=pix)

                    tp = ocr_page.get_textpage_ocr()
                    text = ocr_page.get_text("text", textpage=tp)
                    ocr_doc.close()

                full_text += f"\n\n--- Page {page_num + 1} ---\n\n{text}"
            doc.close()

        elif any(filename.endswith(ext) for ext in supported_images):
            img = fitz.Pixmap(tmp_path)
            if img.alpha:
                img = fitz.Pixmap(img, 0)

            doc = fitz.open()
            page = doc.new_page(width=img.width, height=img.height)
            page.insert_image(fitz.Rect(0, 0, img.width, img.height), pixmap=img)

            tp = page.get_textpage_ocr()
            full_text = page.get_text("text", textpage=tp)
            doc.close()

        else:
            raise ValueError("Unsupported file type")

        return full_text.strip()

    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


@app.get("/health/")
def health():
    return {"status": "ok"}

@app.post("/redis_check/")
def redis_check(data: FingerprintCheck):
    """
    Check if a fingerprint already exists in Redis
    
    Args:
        data (FingerprintCheck): The fingerprint to check, provided as a JSON object with a single field `fingerprint`.
    Returns:
        dict: A dictionary containing a boolean `exists` indicating whether the fingerprint is already processed.
    """
    try:
        exists = redis_conn.sismember(REDIS_PROCESSED_SET, data.fingerprint)
        return {"exists": bool(exists)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/redis_publish/")
def redis_publish(data: FingerprintCheck):
    """
    Publish a fingerprint to Redis processed set.

    Args:
        data (FingerprintCheck): The fingerprint to publish, provided as a JSON object with a single field `fingerprint`.
    Returns:
        dict: A dictionary containing the status of the operation.
    """
    try:
        added = redis_conn.sadd(REDIS_PROCESSED_SET, data.fingerprint)
        if added == 0:
            raise HTTPException(status_code=409, detail="Duplicate email detected")
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/ocr_document/")
def ocr_document(file: UploadFile = File(...), background_tasks: BackgroundTasks = BackgroundTasks()):
    """
    Perform OCR on an uploaded document file asynchronously.

    Args:
        file (UploadFile): The document file to process, which can be a PDF or an image file.
        background_tasks (BackgroundTasks): FastAPI's background task manager to handle OCR processing
            without blocking the request.
    Returns:
        dict: A dictionary containing a unique task ID for tracking the OCR process.
    """
    try:
        contents = file.file.read()
        task_id = str(uuid.uuid4())

        def background_ocr(file_bytes, filename, task_id):
            try:
                text = perform_ocr(file_bytes, filename)
                ocr_results[task_id] = {"status": "completed", "text": text}
            except Exception as e:
                ocr_results[task_id] = {"status": "failed", "error": str(e)}

        ocr_results[task_id] = {"status": "processing", "text": None}
        background_tasks.add_task(background_ocr, contents, file.filename, task_id)

        return {"task_id": task_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OCR processing failed: {e}")
    
@app.get("/ocr_result/{task_id}")
def get_ocr_result(task_id: str):
    """
    Get the OCR result for a specific task ID.

    Args:
        task_id (str): The unique identifier for the OCR task.
    Returns:
        dict: A dictionary containing the OCR result with keys:
            - status: "completed" or "failed"
            - text: The extracted text if successful, or None if failed.
            - error: Error message if the task failed.
    """
    result = ocr_results.get(task_id)
    if not result:
        raise HTTPException(status_code=404, detail="Task ID not found")
    return result


@app.post("/classify/", response_model=ClassifiedResult)
def classify(data: EmailText):
    """
    Classify the email content and extract relevant financial information.

    Args:
        data (EmailText): The email content to classify, provided as a JSON object with a single field `text`.
    Returns:
        ClassifiedResult: A structured response containing the classified information with keys:
            - text: Short description of the transaction.
            - date: Date of the transaction in "YYYY-MM-DD" format.
            - amount: Amount of the transaction as a float.
            - currency: 3-letter ISO currency code (e.g., USD, SGD).
            - vendor: Name of the merchant or party involved in the transaction.
            - ttype: Type of transaction, either "Debit" or "Credit".
            - referenceid: Transaction ID or Reference ID.
            - label: Category of the transaction (e.g., Meals & Entertainment, Transport).
    Raises:
        HTTPException: If the input data is invalid, if a duplicate email is detected, 
        or if an error occurs during processing.
    """
    try:
        # First, check if we've already processed this email
        exists = redis_conn.sismember(REDIS_PROCESSED_SET, data.fingerprint)
        if exists:
            raise HTTPException(status_code=409, detail="Email already processed")
        
        # Add to processed set immediately to prevent race conditions
        redis_conn.sadd(REDIS_PROCESSED_SET, data.fingerprint)
        
        # Process the email
        result = classify_email(data.text, data.date)
        validated = ClassifiedResult(**result)
        entry_with_fingerprint = validated.model_dump()
        entry_with_fingerprint["fingerprint"] = data.fingerprint

        save_entry(entry_with_fingerprint)
        publish_entry(entry_with_fingerprint)
        
        return entry_with_fingerprint
    
    except HTTPException:
        raise

    except Exception as e:
        redis_conn.srem(REDIS_PROCESSED_SET, data.fingerprint)
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))