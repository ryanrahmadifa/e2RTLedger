from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated
import operator
import re
import json
import os
import requests

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL_NAME = "openai/gpt-4.1-mini"


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
You are an intelligent financial data extraction assistant.

Given the following raw text from an email and OCR-processed attachments, extract the following fields accurately as JSON:

- "text": a short description of the transaction
- "date": transaction date in YYYY-MM-DD format (Use the email date {state["date"] if state["date"] else "None"} if missing)
- "amount": transaction amount as a float (0.00 if missing)
- "currency": 3-letter ISO currency code (e.g., USD, SGD, if missing, use "None")
- "vendor": merchant or party involved for transaction with EARLYBIRD AI PTE LTD (if missing, use "None")
- "ttype": "Debit" or "Credit" from the perspective of EARLYBIRD AI PTE LTD (if missing, use "None")
- "referenceid": string of unique transaction or invoice identifier (if missing, use "None")

IMPORTANT: Return ONLY the JSON object without any explanation, formatting, or additional text. Do not include any markdown formatting or explanatory text.
"""

    user_prompt = f"""
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

Given the transaction description, vendor name, and other context, classify the transaction into one of these categories:

- Meals & Entertainment
- Transport
- SaaS
- Travel
- Office
- Other

IMPORTANT: Return ONLY a JSON object with a "label" field containing one of the categories above. Do not include any explanation, formatting, or additional text.

JSON:"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "{\"text\": \"" + input_data.get("text", "") + "\"}"}
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