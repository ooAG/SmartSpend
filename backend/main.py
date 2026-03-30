import os
import shutil
import calendar
import asyncio
import uvicorn
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, Form, Request, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, asc

from backend.db import Base, engine, SessionLocal
from backend.models import Transaction, User, Reminder
from backend.parser import parse_sms
from backend.auth import router as auth_router, get_current_user
from backend.excel_parser import extract_transactions_from_excel
from backend.telegram_bot import app as bot_app  # Ensure handlers are added in its file

# --- LIFESPAN MANAGER ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handles startup and shutdown of the Telegram Bot."""
    print("🤖 [System] Initializing Telegram Bot...")
    try:
        # Start the bot components manually within the FastAPI loop
        await bot_app.initialize()
        await bot_app.start()
        await bot_app.updater.start_polling(drop_pending_updates=True)
        print("✅ [System] Bot is now online and polling.")
    except Exception as e:
        print(f"❌ [System] Bot failed to start: {e}")
    
    yield  # --- Server is now running ---

    print("🛑 [System] Shutting down Telegram Bot...")
    await bot_app.updater.stop()
    await bot_app.stop()
    await bot_app.shutdown()
    print("✅ [System] Shutdown complete.")

# --- APP SETUP ---
app = FastAPI(lifespan=lifespan)
app.include_router(auth_router)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
template_dir = os.path.join(BASE_DIR, "..", "templates")
templates = Jinja2Templates(directory=template_dir)

Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- ROUTES ---

@app.get("/", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse(request=request, name="login.html")

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(
    request: Request, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user),
    sort_by: str = "created_at",
    order: str = "desc",
    view: str = "all",
    month: int = 0,
    year: int = datetime.now().year
):
    query = db.query(Transaction).filter(Transaction.user_id == current_user.id)

    if month > 0:
        last_day = calendar.monthrange(year, month)[1]
        start_date = datetime(year, month, 1)
        end_date = datetime(year, month, last_day, 23, 59, 59)
        query = query.filter(Transaction.created_at >= start_date, Transaction.created_at <= end_date)
    else:
        start_date = datetime(year, 1, 1)
        end_date = datetime(year, 12, 31, 23, 59, 59)
        query = query.filter(Transaction.created_at >= start_date, Transaction.created_at <= end_date)

    if view == "debit":
        query = query.filter(Transaction.type == "debit")
    elif view == "credit":
        query = query.filter(Transaction.type == "credit")

    column = getattr(Transaction, sort_by)
    query = query.order_by(desc(column) if order == "desc" else asc(column))

    txns = query.all()
    reminders = db.query(Reminder).filter(Reminder.user_id == current_user.id).all()

    total_income = sum(t.amount for t in txns if t.type == 'credit')
    total_expense = sum(t.amount for t in txns if t.type == 'debit')

    return templates.TemplateResponse(
        request=request, name="dashboard.html",
        context={
            "transactions": txns, "reminders": reminders, "user": current_user,
            "total_income": total_income, "total_expense": total_expense,
            "net_balance": total_income - total_expense, "current_view": view,
            "current_sort": sort_by, "current_order": order,
            "current_month": month, "current_year": year
        }
    )

@app.get("/api/analytics")
def api_analytics(month: int = 0, year: int = datetime.now().year, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    exp_query = db.query(Transaction.category, func.sum(Transaction.amount)).filter(Transaction.user_id == current_user.id, Transaction.type == 'debit')
    inc_query = db.query(Transaction.category, func.sum(Transaction.amount)).filter(Transaction.user_id == current_user.id, Transaction.type == 'credit')

    if month > 0:
        last_day = calendar.monthrange(year, month)[1]
        start, end = datetime(year, month, 1), datetime(year, month, last_day, 23, 59, 59)
    else:
        start, end = datetime(year, 1, 1), datetime(year, 12, 31, 23, 59, 59)
        
    exp_query = exp_query.filter(Transaction.created_at >= start, Transaction.created_at <= end)
    inc_query = inc_query.filter(Transaction.created_at >= start, Transaction.created_at <= end)

    return {
        "expenses": {"labels": [d[0].title() for d in exp_query.group_by(Transaction.category).all()], "values": [float(d[1]) for d in exp_query.group_by(Transaction.category).all()]},
        "incomes": {"labels": [d[0].title() for d in inc_query.group_by(Transaction.category).all()], "values": [float(d[1]) for d in inc_query.group_by(Transaction.category).all()]}
    }

@app.post("/api/upload_statement")
async def upload_statement(file: UploadFile = File(...), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    temp_path = f"temp_{file.filename}"
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    try:
        extracted_data = extract_transactions_from_excel(temp_path)
        for item in extracted_data:
            txn_date = item['date'] if isinstance(item['date'], datetime) else datetime.utcnow()
            db.add(Transaction(
                user_id=current_user.id, amount=item['amount'], type=item['type'],
                merchant=item['merchant'], category=item['category'], created_at=txn_date 
            ))
        db.commit()
        if os.path.exists(temp_path): os.remove(temp_path)
        return {"status": "success", "count": len(extracted_data)}
    except Exception as e:
        if os.path.exists(temp_path): os.remove(temp_path)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/parse_sms")
def api_parse_sms(text: str = Form(...)):
    parsed = parse_sms(text)
    return {
        "amount": parsed["amount"],
        "type": parsed["type"],
        "merchant": parsed["merchant"],
        "category": parsed.get("category", "Others") 
    }

@app.post("/api/save_transaction")
def api_save_transaction(
    amount: float = Form(...), type: str = Form(...), merchant: str = Form(...), 
    category: str = Form(...), notes: str = Form(None), txn_id: int = Form(None), 
    txn_date: str = Form(None), db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    final_date = datetime.utcnow()
    if txn_date:
        try: final_date = datetime.strptime(txn_date, "%Y-%m-%d")
        except ValueError: pass

    if txn_id:
        txn = db.query(Transaction).filter(Transaction.id == txn_id, Transaction.user_id == current_user.id).first()
        if txn:
            txn.amount, txn.type, txn.merchant, txn.category, txn.notes, txn.created_at = \
                amount, type, merchant, category, notes, final_date
    else:
        db.add(Transaction(
            user_id=current_user.id, amount=amount, type=type, 
            merchant=merchant, category=category, notes=notes, created_at=final_date
        ))
    db.commit()
    return {"status": "success"}

@app.post("/api/delete_transaction")
def api_delete_transaction(txn_id: int = Form(...), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    db.query(Transaction).filter(Transaction.id == txn_id, Transaction.user_id == current_user.id).delete()
    db.commit()
    return {"status": "deleted"}

@app.get("/api/bot/get_user")
def bot_get_user(telegram_id: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.telegram_id == str(telegram_id)).first()
    if not user: raise HTTPException(status_code=404, detail="User not linked")
    return {"id": user.id, "email": user.email}

@app.post("/api/bot/bind")
def bot_bind_user(email: str = Form(...), telegram_id: str = Form(...), db: Session = Depends(get_db)):
    clean_email = email.strip().lower()
    user = db.query(User).filter(User.email == clean_email).first()
    if not user: raise HTTPException(status_code=404, detail="Email not found")
    user.telegram_id = str(telegram_id)
    db.commit()
    return {"status": "bound", "email": clean_email}

# --- EXECUTION ---
if __name__ == "__main__":
    print("🌐 [System] Launching Unified SmartSpend Server...")
    # reload=False is required to keep the lifespan task stable
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=False)