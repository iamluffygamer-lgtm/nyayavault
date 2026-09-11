from pydantic import BaseModel
import uuid
from typing import Optional


class ChainVerificationResult(BaseModel):
    status: str
    stored_hash: str
    computed_hash: str
    on_chain_hash: Optional[str]
    tx_hash: Optional[str]
    block_number: Optional[int]
    detail: str


class AnchorStatusRead(BaseModel):
    status: str
    tx_hash: Optional[str]
    block_number: Optional[int]
    error_message: Optional[str]

