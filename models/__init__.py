from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime

# Use relative import to access Base from the parent package
from database import Base


class SmdKeyBuy(Base):
	__tablename__ = 'smd_key_buy'
	__table_args__ = {"sqlite_autoincrement": True}

	id = Column(Integer, primary_key=True, index=True)
	symbol = Column(String(50), index=True, nullable=False)
	market = Column(String(50), nullable=False, default='NSE')
	spot_price = Column(Float, nullable=False)
	atm_strike = Column(Float, nullable=False)
	otm_call_strike = Column(Float, nullable=False)
	otm_put_strike = Column(Float, nullable=False)
	otm_call_close = Column(Float, nullable=False)
	otm_put_close = Column(Float, nullable=False)
	smd_key_buy = Column(Float, nullable=False)
	created_at = Column(DateTime, default=datetime.utcnow, index=True)


__all__ = ["SmdKeyBuy"]
