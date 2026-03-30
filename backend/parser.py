import re

def parse_sms(text: str):
    text_lower = text.lower()

    # 1. Amount
    amount_match = re.search(r'(rs\.?|inr)\s?(\d+[.,]?\d*)', text_lower)
    amount = float(amount_match.group(2).replace(",", "")) if amount_match else 0

    # 2. Type
    if any(x in text_lower for x in ["debited", "spent", "purchase", "sent", "paid"]):
        txn_type = "debit"
    elif any(x in text_lower for x in ["credited", "received"]):
        txn_type = "credit"
    else:
        txn_type = "unknown"

    # 3. Merchant / Source
    merchant = "unknown"

    # PATTERN A: Raw UPI String format (e.g., UPI/DR/608574416954/ADARSH GOEL/...)
    # This splits the slashes and perfectly extracts the 4th item (the payee name).
    upi_match = re.search(r'UPI/(?:[a-zA-Z0-9\-]+/)?\d+/([^/]+)', text, re.IGNORECASE)
    
    if upi_match:
        merchant = upi_match.group(1).strip()
    else:
        # PATTERN B: Sentence format (e.g., "spent at Zomato" or "received from user@upi")
        merchant_match = re.search(r'(?:at|to|from)\s+([a-zA-Z0-9@.\-\s]+?)(?:\n| on | ref | sms |$)', text, re.IGNORECASE)
        
        if merchant_match:
            merchant_raw = merchant_match.group(1).strip()
            # Security Check: Ignore if the parser accidentally grabs your "A/c" or "Account" number!
            if not re.match(r'^(a/c|ac|account)\b', merchant_raw, re.IGNORECASE) and "block" not in merchant_raw.lower():
                merchant = merchant_raw

    return {
        "amount": amount,
        "type": txn_type,
        "merchant": merchant.lower().title() if merchant != "unknown" else "Unknown"
    }