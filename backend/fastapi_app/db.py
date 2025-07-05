from sqlalchemy import create_engine, Column, Integer, String, Text, Float, DateTime
from sqlalchemy.sql import func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
import os
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://ledger:ledgerpw@localhost:5432/ledgerdb")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class LedgerEntry(Base):
    """
    Represents a single entry in the ledger.
    Each entry corresponds to a financial transaction with various attributes.
    Attributes:
        id: Unique identifier for the entry.
        text: Description of the transaction.
        date: Date of the transaction in YYYY-MM-DD format.
        amount: Amount of the transaction.
        currency: Currency of the transaction (e.g., USD, SGD).
        vendor: Name of the vendor or party involved in the transaction.
        ttype: Type of transaction, either "Debit" or "Credit".
        referenceid: Unique reference ID for the transaction.
        label: Category of the transaction (e.g., Meals & Entertainment, Transport).
        fingerprint: Unique fingerprint for the entry, used to prevent duplicates.
        created_at: Timestamp when the entry was created.
    """
    __tablename__ = "ledger"
    id = Column(Integer, primary_key=True, index=True)
    text = Column(Text)
    date = Column(String)
    amount = Column(Float)
    currency = Column(String)
    vendor = Column(String)
    ttype = Column(String)
    referenceid = Column(String)
    label = Column(String)
    fingerprint = Column(String, nullable=False, index=True, unique=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

Base.metadata.create_all(bind=engine)

def save_entry(data):
    """
    Save a new ledger entry to the database.

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
            - fingerprint (str): Unique fingerprint for the entry, used to prevent duplicates.
    """
    db = SessionLocal()
    try:
        logger.info("Attempting to save entry: %s", data)

        # Print all existing rows
        existing_rows = db.query(LedgerEntry).all()
        logger.info("Current rows in DB (%d):", len(existing_rows))
        for row in existing_rows:
            logger.info("Row ID %s | Fingerprint: %s | Vendor: %s | Amount: %.2f | Date: %s",
                        row.id, row.fingerprint, row.vendor, row.amount, row.date)

        # Attempt to insert
        entry = LedgerEntry(
            text=data["text"],
            date=data["date"],
            amount=data["amount"],
            currency=data["currency"],
            vendor=data["vendor"],
            ttype=data["ttype"],
            referenceid=data["referenceid"],
            label=data["label"],
            fingerprint=data["fingerprint"]
        )
        db.add(entry)
        db.commit()
        logger.info("Entry committed successfully.")
    except IntegrityError:
        db.rollback()
        logger.warning("Duplicate fingerprint detected — skipping entry: %s", data["fingerprint"])
    except Exception as e:
        db.rollback()
        logger.exception("Failed to save entry due to exception.")
        raise
    finally:
        db.close()