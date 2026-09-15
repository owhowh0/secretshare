# the generator of the unpredictalbe unique identifiers encoding them into base64 string
import secrets 

def new_payload_id() -> str:
    return secrets.token_urlsafe(32)