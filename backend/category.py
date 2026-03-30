def detect_category(merchant: str):
    m = merchant.lower()

    if any(x in m for x in ["swiggy", "zomato", "restaurant"]):
        return "food"
    if any(x in m for x in ["uber", "ola", "rapido"]):
        return "transport"
    if any(x in m for x in ["amazon", "flipkart"]):
        return "shopping"
    
    return "others"