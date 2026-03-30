import pandas as pd
import re
from datetime import datetime

def parse_narration_flexible(raw_narration):

    if not raw_narration or pd.isna(raw_narration):
        return "Unknown", "Transfers"

    # Use the full string as the starting point
    name = str(raw_narration).strip()

    # Remove ONLY long reference numbers (10+ digits)
    name = re.sub(r'\d{10,}', '', name)
    
    # Clean trailing bank noise like "BY", "TO", or "Ref"
    name = re.sub(r'\s(BY|TO|TRANSFER|Ref).*', '', name, flags=re.I)
    
    # Return the full cleaned name and force "Transfers" as category
    return ' '.join(name.split()).strip(), "Transfers"

def extract_transactions_from_excel(file_path):
    try:
        # 1. Load raw data
        df_raw = pd.read_excel(file_path, header=None)
        
        # 2. Find the header row dynamically
        header_index = None
        for i in range(min(len(df_raw), 40)):
            row_str = [str(val).lower().strip() for val in df_raw.iloc[i].values]
            if 'date' in row_str and ('narration' in row_str or 'particulars' in row_str):
                header_index = i
                break
        
        if header_index is None:
            return []

        # 3. Read data and clean columns
        df = pd.read_excel(file_path, skiprows=header_index)
        df.columns = [str(c).lower().strip() for c in df.columns]

        # 4. Map columns
        col_map = {
            'date': next((c for c in df.columns if 'date' in c), None),
            'narration': next((c for c in df.columns if 'narration' in c or 'particulars' in c), None),
            'withdrawal': next((c for c in df.columns if 'withdrawal' in c or 'debit' in c), None),
            'deposit': next((c for c in df.columns if 'deposit' in c or 'credit' in c), None)
        }

        transactions = []
        for _, row in df.iterrows():
            raw_date = row.get(col_map['date'])
            
            # Skip empty or footer rows
            if pd.isna(raw_date) or str(raw_date).strip() == "" or str(raw_date).startswith('*'):
                continue

            # 5. Correct Date Parsing
            try:
                if isinstance(raw_date, datetime):
                    final_date = raw_date
                else:
                    final_date = pd.to_datetime(str(raw_date).strip(), dayfirst=True).to_pydatetime()
            except:
                continue 

            # 6. Amount handling (Clean commas and spaces)
            def to_num(val):
                if pd.isna(val): return 0
                return pd.to_numeric(str(val).replace(',', '').strip(), errors='coerce') or 0

            withdrawal = to_num(row.get(col_map['withdrawal'], 0))
            deposit = to_num(row.get(col_map['deposit'], 0))
            
            if withdrawal > 0:
                amount, txn_type = float(withdrawal), "debit"
            elif deposit > 0:
                amount, txn_type = float(deposit), "credit"
            else: 
                continue

            # 7. Apply your new narration/category logic
            narration_str = str(row.get(col_map['narration'], ''))
            m_name, c_name = parse_narration_flexible(narration_str)

            transactions.append({
                "date": final_date,
                "amount": amount,
                "merchant": m_name,
                "type": txn_type,
                "category": c_name # This will always be "Transfers"
            })
            
        return transactions
    except Exception as e:
        print(f"Parser Error: {e}")
        return []