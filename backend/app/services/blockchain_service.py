import uuid
import json
import logging
from pathlib import Path
from web3 import Web3
from app.config import get_settings

logger = logging.getLogger(__name__)


class AnchorResult:
    def __init__(self, status: str, tx_hash: str | None = None, block_number: int | None = None, error: str | None = None):
        self.status = status
        self.tx_hash = tx_hash
        self.block_number = block_number
        self.error = error


class OnChainRecord:
    def __init__(self, case_id: str, document_id: str, version: int, timestamp: int, anchored_by: str):
        self.case_id = case_id
        self.document_id = document_id
        self.version = version
        self.timestamp = timestamp
        self.anchored_by = anchored_by


def get_web3_and_contract():
    settings = get_settings()
    rpc_url = settings.blockchain_rpc_url
    contract_address = settings.blockchain_contract_address

    w3 = Web3(Web3.HTTPProvider(rpc_url))
    
    # Try to load ABI from contract.json written by deployment script
    abi = []
    artifacts_path = Path("/artifacts/contract.json")
    if artifacts_path.exists():
        try:
            with open(artifacts_path, "r") as f:
                data = json.load(f)
                abi = data.get("abi", [])
                if not contract_address:
                    contract_address = data.get("address")
        except BaseException as e:
            logger.error(f"Failed to load contract artifact: {e}")

    if not contract_address or not abi:
        raise ValueError("Blockchain contract address or ABI is missing.")
        
    contract = w3.eth.contract(address=contract_address, abi=abi)
    return w3, contract


def anchor_document_hash(sha256_hash: str, case_id: str, document_id: str, version: int) -> AnchorResult:
    try:
        w3, contract = get_web3_and_contract()
        if not w3.is_connected():
            return AnchorResult(status="FAILED", error="RPC node is unreachable.")

        # In a real app we'd load the private key, but for local hardhat we can use the default first account
        account = w3.eth.accounts[0]
        
        # Ensure hash is 32 bytes (64 hex characters)
        hash_bytes = bytes.fromhex(sha256_hash)
        
        tx_hash = contract.functions.anchorHash(
            hash_bytes, case_id, document_id, version
        ).transact({'from': account})
        
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        
        if receipt.status == 1:
            return AnchorResult(status="ANCHORED", tx_hash=receipt.transactionHash.hex(), block_number=receipt.blockNumber)
        else:
            return AnchorResult(status="FAILED", tx_hash=receipt.transactionHash.hex(), error="Transaction reverted.")
            
    except Exception as e:
        logger.exception("Error anchoring document hash")
        return AnchorResult(status="FAILED", error=str(e))


def verify_on_chain(sha256_hash: str) -> OnChainRecord | None:
    try:
        w3, contract = get_web3_and_contract()
        if not w3.is_connected():
            logger.error("RPC node is unreachable during verification.")
            return None

        hash_bytes = bytes.fromhex(sha256_hash)
        record = contract.functions.getAnchor(hash_bytes).call()
        # Returns: caseId, documentId, version, timestamp, anchoredBy
        return OnChainRecord(
            case_id=record[0],
            document_id=record[1],
            version=record[2],
            timestamp=record[3],
            anchored_by=record[4]
        )
    except Exception as e:
        logger.error(f"Failed to verify on chain or hash not anchored: {e}")
        return None

def anchor_background_task(db_generator_callable, version_id: uuid.UUID):
    # db_generator_callable should return a new Session
    try:
        from app.models.document import DocumentVersion
        from app.models.blockchain import BlockchainAnchor, AnchorStatus
        from app.models.audit import AuditAction, AuditResult
        from app.services import audit_service
        
        db = next(db_generator_callable())
        try:
            version = db.get(DocumentVersion, version_id)
            if not version:
                print(f"VERSION NOT FOUND: {version_id}")
                return

            anchor = version.blockchain_anchor
            if not anchor or anchor.status != AnchorStatus.PENDING:
                print(f"ANCHOR NOT READY: {anchor}")
                return

            # Call anchor_document_hash
            sha256 = version.sha256_hash
            case_id = str(version.document.case_id)
            document_id = str(version.document_id)
            v_num = version.version_number
            
            result = anchor_document_hash(sha256, case_id, document_id, v_num)
            
            anchor.status = AnchorStatus(result.status)
            anchor.tx_hash = result.tx_hash
            anchor.block_number = result.block_number
            if result.error:
                anchor.error_message = result.error
                
            # Audit log
            audit_result = AuditResult.SUCCESS if result.status == "ANCHORED" else AuditResult.FAILURE
            audit_service.record_event(
                db,
                action=AuditAction.ANCHOR_ATTEMPTED,
                entity_type="blockchain_anchor",
                entity_id=anchor.id,
                case_id=version.document.case_id,
                actor_id=version.uploaded_by,
                result=audit_result,
                metadata={
                    "sha256": sha256,
                    "tx_hash": result.tx_hash,
                    "error": result.error
                }
            )
            
            db.commit()
        except Exception as e:
            db.rollback()
            print(f"EXCEPTION: {e}")
            logger.exception("Failed inside anchor background task")
        finally:
            db.close()
    except Exception:
        logger.exception("Could not obtain DB session for background task")

