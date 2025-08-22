import logging
from datetime import datetime
from typing import Optional, Dict, Any

from kiteconnect import KiteConnect

from config.settings import Config
from database import get_session, engine, Base
from models.token_store import TokenStore


class KiteTokenService:
	"""Manages Zerodha Kite access/refresh tokens with DB persistence."""

	def __init__(self):
		self.logger = logging.getLogger(__name__)
		self.api_key = Config.KITE_API_KEY
		self.api_secret = Config.KITE_API_SECRET
		# Ensure tables exist
		Base.metadata.create_all(bind=engine)
		if not self.api_key or not self.api_secret:
			self.logger.warning("Kite API credentials are missing; token operations will fail")

	# ---------------------- DB helpers ---------------------- #
	def _get_row(self) -> Optional[TokenStore]:
		session = get_session()
		try:
			q = session.query(TokenStore)
			if self.api_key:
				q = q.filter(TokenStore.api_key == self.api_key)
			row = q.order_by(TokenStore.id.desc()).first()
			return row
		finally:
			session.close()

	def get_tokens(self) -> Dict[str, Any]:
		row = self._get_row()
		return row.to_dict() if row else {}

	def _save_tokens(self, data: Dict[str, Any]) -> Dict[str, Any]:
		session = get_session()
		try:
			row = self._get_row()
			if not row:
				row = TokenStore()
				session.add(row)
			row.api_key = self.api_key
			row.user_id = data.get('user_id') or data.get('user_id')
			row.access_token = data.get('access_token')
			row.refresh_token = data.get('refresh_token')
			row.public_token = data.get('public_token')
			row.last_refreshed_at = datetime.utcnow()
			session.commit()
			return row.to_dict()
		finally:
			session.close()

	# ---------------------- Kite flows ---------------------- #
	def bootstrap_with_request_token(self, request_token: str) -> Dict[str, Any]:
		"""Use a one-time request_token to get access/refresh tokens and persist them."""
		if not request_token:
			raise ValueError("request_token is required")
		if not self.api_key or not self.api_secret:
			raise RuntimeError("Kite API credentials are not configured")

		kite = KiteConnect(api_key=self.api_key)
		data = kite.generate_session(request_token, api_secret=self.api_secret)
		# data contains access_token, public_token, refresh_token, etc.
		tokens = {
			'user_id': data.get('user_id'),
			'access_token': data.get('access_token'),
			'refresh_token': data.get('refresh_token'),
			'public_token': data.get('public_token'),
		}
		saved = self._save_tokens(tokens)
		self.logger.info("Kite tokens bootstrapped and saved")
		return saved

	def refresh_tokens(self) -> Dict[str, Any]:
		"""Refresh access token using stored refresh token; rotate and persist."""
		if not self.api_key or not self.api_secret:
			raise RuntimeError("Kite API credentials are not configured")
		row = self._get_row()
		if not row or not row.refresh_token:
			raise RuntimeError("No refresh token found; bootstrap required")

		kite = KiteConnect(api_key=self.api_key)
		try:
			data = kite.renew_access_token(row.refresh_token, api_secret=self.api_secret)
		except Exception as e:
			# Some SDKs use 'refresh_access_token'; try alt method name if present
			try:
				data = kite.refresh_access_token(row.refresh_token, api_secret=self.api_secret)  # type: ignore[attr-defined]
			except Exception:
				raise
		tokens = {
			'user_id': data.get('user_id') or row.user_id,
			'access_token': data.get('access_token'),
			'refresh_token': data.get('refresh_token') or row.refresh_token,
			'public_token': data.get('public_token') or row.public_token,
		}
		saved = self._save_tokens(tokens)
		self.logger.info("Kite tokens refreshed")
		return saved

	def set_access_on_client(self, kite_client: KiteConnect) -> bool:
		"""Attach stored access token to a KiteConnect instance. Returns True if set."""
		try:
			tokens = self.get_tokens()
			at = tokens.get('access_token')
			if at:
				kite_client.set_access_token(at)
				return True
			return False
		except Exception:
			return False

	def ensure_valid(self, kite_client: KiteConnect) -> None:
		"""Attempt a light call; on failure, refresh and attach new token once."""
		try:
			kite_client.profile()
		except Exception:
			# Try refresh once
			self.refresh_tokens()
			tokens = self.get_tokens()
			if tokens.get('access_token'):
				kite_client.set_access_token(tokens['access_token'])


# Singleton instance
kite_token_service = KiteTokenService()

