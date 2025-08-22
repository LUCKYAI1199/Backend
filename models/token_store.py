from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime
from database import Base


class TokenStore(Base):
    __tablename__ = 'kite_tokens'

    id = Column(Integer, primary_key=True, index=True)
    api_key = Column(String(128), nullable=True, index=True)
    user_id = Column(String(64), nullable=True, index=True)
    access_token = Column(String(512), nullable=True)
    refresh_token = Column(String(512), nullable=True)
    public_token = Column(String(512), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_refreshed_at = Column(DateTime, nullable=True)

    def to_dict(self):
        return {
            'api_key': self.api_key,
            'user_id': self.user_id,
            'access_token': self.access_token,
            'refresh_token': self.refresh_token,
            'public_token': self.public_token,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'last_refreshed_at': self.last_refreshed_at.isoformat() if self.last_refreshed_at else None,
        }
