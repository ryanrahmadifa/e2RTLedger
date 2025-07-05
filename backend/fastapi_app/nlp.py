import requests
import os
import json
import re

def classify_email(text: str, date: str):
    """
    Classify the email content and extract relevant financial information.

    Args:
        text (str): The raw email content to classify.
    Returns:
        dict: A dictionary containing the classified information with keys:
            - text: Short description of the transaction.
            - date: Date of the transaction in "YYYY-MM-DD" format.
            - amount: Amount of the transaction as a float.
            - currency: 3-letter ISO currency code (e.g., USD, SGD).
            - vendor: Name of the merchant or party involved in the transaction.
            - ttype: Type of transaction, either "Debit" or "Credit".
            - referenceid: Transaction ID or Reference ID.
            - label: Category of the transaction (e.g., Meals & Entertainment, Transport).
    """
    headers = {
        "Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY')}",
        "Content-Type": "application/json",
        "X-Title": "Live Ledger Classifier"
    }

    payload = {
        "model": "google/gemini-2.5-flash-lite-preview-06-17",
        "messages": [
            {"role": "system", "content": 
             """
             You are an intelligent expense extraction agent for EARLYBIRD AI PTE LTD.
             You will build a financial ledger for the company EARLYBIRD AI PTE LTD.
             Given a raw email, extract the following as JSON:
                {
                "text": Short description of the transaction (string)
                "date": "YYYY-MM-DD (string)",
                "amount": float of transaction amount (float),
                "currency": 3-letter ISO (USD, SGD, IDR, etc.),
                "vendor": Merchant's or the party that does the transaction's name (string),
                "ttype": Type of transaction, either "Debit" or "Credit" from the POV of EARLYBIRD AI PTE LTD (string),
                "referenceid": Transaction ID or Reference ID (string),
                "category": Classify the expense email into Meals & Entertainment, Transport, SaaS, Travel, Office, or Other (string)
                }

                It is mandatory to return said JSON object without any explanation, formatting, or code block. Do NOT include triple backticks.
                If no value is found for a key, return string of "None" as the value for strings and 0.00 for floats.
                Return the truthful JSON.
             """},
            {"role": "user", "content": text}
        ]
    }

    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions", 
        headers=headers, 
        json=payload
    )
    response.raise_for_status()

    content = response.json()['choices'][0]['message']['content']
    content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip(), flags=re.MULTILINE)

    print(f"HELLO RYAN {content}")
    label = json.loads(content)

    return {
        "text": label.get("text", "None"),
        "date": label.get("date") if label.get("date") != "None" else date,
        "amount": label.get("amount", 0.00),
        "currency": label.get("currency", "None"),
        "vendor": label.get("vendor", "None"),
        "ttype": label.get("ttype", "None"),
        "referenceid": label.get("referenceid", "None"),
        "label": label.get("category", "None")
    }
