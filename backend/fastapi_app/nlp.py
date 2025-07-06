from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated
import operator
import re
import json
import os
import requests

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL_NAME = "anthropic/claude-3.5-haiku"


def extract_json_from_text(text):
    """Extract JSON from text that may contain explanatory content"""
    # Try to find JSON block in the text
    json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
    matches = re.findall(json_pattern, text, re.DOTALL)
    
    for match in matches:
        try:
            parsed = json.loads(match)
            return match
        except json.JSONDecodeError:
            continue
    
    raise ValueError("No valid JSON found in response")


def call_openrouter(messages, max_retries=3):
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "X-Title": "Live Ledger Agent",
    }
    payload = {
        "model": MODEL_NAME,
        "messages": messages,
        "max_tokens": 10000,
        "temperature": 0.1,
    }
    
    for attempt in range(max_retries):
        try:
            resp = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=30)
            resp.raise_for_status()
            
            response_data = resp.json()
            
            if 'choices' not in response_data or not response_data['choices']:
                raise ValueError("No choices in response")
            
            content = response_data['choices'][0]['message']['content']
            
            if not content or not content.strip():
                raise ValueError("Empty response content")
            
            content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip(), flags=re.MULTILINE)
            
            try:
                json_content = extract_json_from_text(content)
                json.loads(json_content)
                return json_content
            except (json.JSONDecodeError, ValueError) as e:
                if attempt < max_retries - 1:
                    print(f"JSON extraction failed, retrying... (attempt {attempt + 1}/{max_retries})")
                    print(f"Content received: {content[:500]}...")
                    continue
                else:
                    raise ValueError(f"Invalid JSON after {max_retries} attempts: {content}")
            
        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                print(f"Request failed, retrying... (attempt {attempt + 1}/{max_retries}): {e}")
                continue
            else:
                raise
        except (KeyError, ValueError) as e:
            if attempt < max_retries - 1:
                print(f"Response parsing failed, retrying... (attempt {attempt + 1}/{max_retries}): {e}")
                continue
            else:
                raise


class TransactionState(TypedDict):
    input_text: str
    date: str
    extracted_data: dict
    final_result: dict
    errors: Annotated[list, operator.add]


def entity_extractor_node(state: TransactionState) -> TransactionState:
    """Extract entities from the input text"""
    input_text = state["input_text"]
    
    system_prompt = f"""
    You are an intelligent financial data extraction assistant. You are skilled in extracting structured financial 
    transaction data from unstructured text, such as emails or OCR-processed documents.
    """

    user_prompt = f"""
    Given the following raw text from an email and OCR-processed attachments, extract the following fields accurately as JSON:

    - "text": a short description of the transaction
    - "date": transaction date in YYYY-MM-DD format (Use the email date {state["date"] if state["date"] else "None"} if missing)
    - "amount": transaction amount as a float (0.00 if missing)
    - "currency": 3-letter ISO currency code (e.g., USD, SGD, if missing, use "None")
    - "vendor": merchant or party involved for transaction with EARLYBIRD AI PTE LTD (if missing, use "None")
    - "ttype": "Debit" or "Credit" from EARLYBIRD AI PTE LTD's perspective:
    * "Debit" = Money going OUT of EARLYBIRD AI PTE LTD (expenses, payments made, purchases)
    * "Credit" = Money coming INTO EARLYBIRD AI PTE LTD (income, payments received, refunds)
    - "referenceid": string of unique transaction or invoice identifier (if missing, use "None")

    EXAMPLES:

    Example 1 - Invoice received (money going out):
    Raw text: "Invoice #INV-2024-001 from Office Supplies Co. for 250.00 EUR dated 2024-03-15. Payment due for office equipment purchase."
    JSON: {{"text": "Office equipment purchase", "date": "2024-03-15", "amount": 250.00, "currency": "EUR", "vendor": "Office Supplies Co.", "ttype": "Debit", "referenceid": "INV-2024-001"}}

    Example 2 - Payment received (money coming in):
    Raw text: "Payment received from Client ABC to EARLYBIRD AI PTE LTD. for services rendered. Amount: SGD 1,500.00. Reference: PAY-2024-445. Date: 2024-03-20"
    JSON: {{"text": "Payment received for services", "date": "2024-03-20", "amount": 1500.00, "currency": "SGD", "vendor": "Client ABC", "ttype": "Credit", "referenceid": "PAY-2024-445"}}

    Example 3 - Refund received (money coming in):
    Raw text: "Refund processed by Software Provider Ltd. to EARLYBIRD AI PTE LTD. Amount: USD 89.99. Refund ID: REF-789. Date: 2024-03-18"
    JSON: {{"text": "Refund from software provider", "date": "2024-03-18", "amount": 89.99, "currency": "USD", "vendor": "Software Provider Ltd.", "ttype": "Credit", "referenceid": "REF-789"}}

    Example 4 - Expense payment (money going out):
    Raw text: "Monthly subscription fee charged by Cloud Services Inc. $45.00 USD. Transaction ID: TXN-456789. Date: 2024-03-25"
    JSON: {{"text": "Monthly subscription fee", "date": "2024-03-25", "amount": 45.00, "currency": "USD", "vendor": "Cloud Services Inc.", "ttype": "Debit", "referenceid": "TXN-456789"}}

    IMPORTANT: Return ONLY the JSON object without any explanation, formatting, or additional text. Do not include any markdown formatting or explanatory text.

    Raw text from email and OCR attachments:
    \"\"\"
    {input_text}
    \"\"\"

    JSON:"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    try:
        print(f"EntityExtractor: Processing text length: {len(input_text)}")
        
        raw_output = call_openrouter(messages)
        print(f"EntityExtractor: Raw output: {raw_output[:200]}...")
        
        extracted_data = json.loads(raw_output)
        print(f"EntityExtractor: Successfully parsed JSON")
        
        return {
            **state,
            "extracted_data": extracted_data,
            "errors": []
        }
    except Exception as e:
        print(f"EntityExtractor: Error occurred: {type(e).__name__}: {str(e)}")
        default_data = {
            "text": "Error extracting data",
            "date": "None",
            "amount": 0.00,
            "currency": "None",
            "vendor": "None",
            "ttype": "None",
            "referenceid": "None"
        }
        return {
            **state,
            "extracted_data": default_data,
            "errors": [f"EntityExtractor error: {str(e)}"]
        }


def categorizer_node(state: TransactionState) -> TransactionState:
    """Categorize the transaction"""
    input_data = state["extracted_data"]
    input_text = state["input_text"]
    
    system_prompt = f"""
    You are an expert financial transaction categorization assistant.
    You are skilled in classifying transactions into predefined categories based on the extracted data.
    """
    
    user_prompt = f"""# Expense Classification Prompt

        You are an expert expense categorization assistant. Your task is to classify transaction data into one of the following categories based on the description, merchant, and amount:

        ## Categories:
        - **Meals & Entertainment**: Restaurants, bars, catering, team meals, client dinners, entertainment venues
        - **Transport**: Uber, taxi, gas, parking, public transit, car rentals, vehicle maintenance
        - **SaaS**: Software subscriptions, cloud services, online tools, digital platforms
        - **Travel**: Hotels, flights, airfare, accommodation, travel booking sites
        - **Office**: Office supplies, equipment, furniture, utilities, rent, phone bills
        - **Other**: Any expense that doesn't clearly fit the above categories

        ## Instructions:
        1. Analyze the transaction description, merchant name, and amount
        2. Consider the business context and typical expense patterns
        3. Choose the most appropriate category
        4. Return only a JSON object with a "label" field

        ## Examples:

        **Input:** "UBER TRIP - SAN FRANCISCO, $23.45"
        **Output:** {{"label": "Transport"}}

        **Input:** "STARBUCKS COFFEE - DOWNTOWN, $8.99"
        **Output:** {{"label": "Meals & Entertainment"}}

        **Input:** "ADOBE CREATIVE CLOUD SUBSCRIPTION, $52.99"
        **Output:** {{"label": "SaaS"}}

        **Input:** "MARRIOTT HOTEL - CHICAGO, $189.00"
        **Output:** {{"label": "Travel"}}

        **Input:** "STAPLES OFFICE SUPPLIES, $45.67"
        **Output:** {{"label": "Office"}}

        **Input:** "AMAZON WEB SERVICES, $127.83"
        **Output:** {{"label": "SaaS"}}

        **Input:** "SHELL GAS STATION, $65.22"
        **Output:** {{"label": "Transport"}}

        **Input:** "BLUE BOTTLE COFFEE - CLIENT MEETING, $34.50"
        **Output:** {{"label": "Meals & Entertainment"}}

        **Input:** "UNITED AIRLINES - FLIGHT TO NYC, $456.00"
        **Output:** {{"label": "Travel"}}

        **Input:** "VERIZON BUSINESS - OFFICE PHONE, $89.99"
        **Output:** {{"label": "Office"}}

        **Input:** "MICROSOFT OFFICE 365, $15.00"
        **Output:** {{"label": "SaaS"}}

        **Input:** "WALMART - MISCELLANEOUS ITEMS, $23.45"
        **Output:** {{"label": "Other"}}

        ## Task:
        Classify the following transaction data:

        ```
        {input_text}
        ```

        Return only a JSON object with a "label" field containing the category."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    try:
        print(f"Categorizer: Processing data: {json.dumps(input_data, indent=2)}")
        
        raw_output = call_openrouter(messages)
        print(f"Categorizer: Raw output: {raw_output[:200]}...")
        
        category_result = json.loads(raw_output)
        print(f"Categorizer: Successfully parsed JSON")
        
        final_result = {
            **input_data,
            "label": category_result.get("label", "Other")
        }
        
        return {
            **state,
            "final_result": final_result
        }
    except Exception as e:
        print(f"Categorizer: Error occurred: {type(e).__name__}: {str(e)}")
        final_result = {
            **input_data,
            "label": "Other"
        }
        return {
            **state,
            "final_result": final_result,
            "errors": state.get("errors", []) + [f"Categorizer error: {str(e)}"]
        }

def create_workflow():
    workflow = StateGraph(TransactionState)
    
    workflow.add_node("extract_entities", entity_extractor_node)
    workflow.add_node("categorize", categorizer_node)

    workflow.add_edge("extract_entities", "categorize")
    workflow.add_edge("categorize", END)
    
    workflow.set_entry_point("extract_entities")
    
    return workflow.compile()

transaction_workflow = create_workflow()


def classify_email_agentic(raw_text: str, date: str = None) -> dict:
    """
    Process raw email text through the LangGraph workflow to extract and classify transaction data.
    
    Args:
        raw_text: Raw email/document text
        date: Optional email date for disambiguation
        
    Returns:
        Dictionary containing extracted and classified transaction data
    """
    if not OPENROUTER_API_KEY:
        print("Warning: OPENROUTER_API_KEY environment variable is not set")
        return {
            "text": "API key not configured",
            "date": "None",
            "amount": 0.00,
            "currency": "None",
            "vendor": "None",
            "ttype": "None",
            "referenceid": "None",
            "label": "Other"
        }
    
    initial_state = {
        "input_text": raw_text,
        "date": date,
        "extracted_data": {},
        "final_result": {},
        "errors": []
    }
    
    print(f"Starting workflow with input text: {raw_text[:100]}...")
    result = transaction_workflow.invoke(initial_state)
    
    if result.get("errors"):
        print("Workflow errors:", result["errors"])
    
    return result["final_result"]


if __name__ == "__main__":
    # Test with sample data
    sample_email_text = "Your invoice from ACME Corp on 2025-07-05 for USD 123.45. Transaction ID 98765."
    result = classify_email_agentic(sample_email_text, "2025-07-05")
    print("Final classified output:", json.dumps(result, indent=2))