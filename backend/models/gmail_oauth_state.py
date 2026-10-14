from datetime import datetime
from database import db


class GmailOAuthState(db.Model):
    __tablename__ = "gmail_oauth_states"
    state = db.Column(db.String(64), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
