"""Security service for credential storage and data encryption."""

import os
import json
import base64
from typing import Dict, Any, Optional, Union
from pathlib import Path
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import logging

from app.config import settings
from app.database_utils import handle_db_errors
from app.services.audit_service import audit_service, AuditEventType, AuditSeverity

logger = logging.getLogger(__name__)


class SecurityService:
    """Service for handling encryption, credential storage, and security operations."""
    
    def __init__(self):
        self.credentials_dir = Path(settings.data_dir) / "credentials"
        self.credentials_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize encryption key
        self._encryption_key = None
        self._fernet = None
        self._initialize_encryption()
    
    def _initialize_encryption(self):
        """Initialize encryption key and Fernet cipher."""
        try:
            # Try to load existing key
            key_file = self.credentials_dir / "encryption.key"
            
            if key_file.exists():
                with open(key_file, 'rb') as f:
                    self._encryption_key = f.read()
            else:
                # Generate new key
                self._encryption_key = Fernet.generate_key()
                
                # Save key securely
                with open(key_file, 'wb') as f:
                    f.write(self._encryption_key)
                
                # Set restrictive permissions (Unix-like systems)
                try:
                    os.chmod(key_file, 0o600)
                except OSError:
                    logger.warning("Could not set restrictive permissions on key file")
            
            self._fernet = Fernet(self._encryption_key)
            logger.info("Encryption initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize encryption: {str(e)}")
            raise
    
    def encrypt_data(self, data: Union[str, bytes, Dict[str, Any]]) -> str:
        """
        Encrypt data using Fernet symmetric encryption.
        
        Args:
            data: Data to encrypt (string, bytes, or dict)
            
        Returns:
            Base64-encoded encrypted data
        """
        try:
            # Convert data to bytes if necessary
            if isinstance(data, dict):
                data_bytes = json.dumps(data).encode('utf-8')
            elif isinstance(data, str):
                data_bytes = data.encode('utf-8')
            else:
                data_bytes = data
            
            # Encrypt and encode
            encrypted_data = self._fernet.encrypt(data_bytes)
            return base64.b64encode(encrypted_data).decode('utf-8')
            
        except Exception as e:
            logger.error(f"Encryption failed: {str(e)}")
            raise
    
    def decrypt_data(self, encrypted_data: str, return_type: str = "string") -> Union[str, bytes, Dict[str, Any]]:
        """
        Decrypt data using Fernet symmetric encryption.
        
        Args:
            encrypted_data: Base64-encoded encrypted data
            return_type: Type to return ("string", "bytes", or "dict")
            
        Returns:
            Decrypted data in specified format
        """
        try:
            # Decode and decrypt
            encrypted_bytes = base64.b64decode(encrypted_data.encode('utf-8'))
            decrypted_bytes = self._fernet.decrypt(encrypted_bytes)
            
            # Return in requested format
            if return_type == "bytes":
                return decrypted_bytes
            elif return_type == "dict":
                return json.loads(decrypted_bytes.decode('utf-8'))
            else:  # string
                return decrypted_bytes.decode('utf-8')
                
        except Exception as e:
            logger.error(f"Decryption failed: {str(e)}")
            raise
    
    def store_credentials(self, service_name: str, credentials: Dict[str, Any]) -> bool:
        """
        Store encrypted credentials for a service.
        
        Args:
            service_name: Name of the service (e.g., "linkedin", "indeed")
            credentials: Dictionary containing credential data
            
        Returns:
            True if credentials were stored successfully
        """
        try:
            # Encrypt credentials
            encrypted_credentials = self.encrypt_data(credentials)
            
            # Store in secure file
            credentials_file = self.credentials_dir / f"{service_name}.cred"
            
            credential_data = {
                "service_name": service_name,
                "encrypted_data": encrypted_credentials,
                "created_at": self._get_current_timestamp(),
                "updated_at": self._get_current_timestamp()
            }
            
            with open(credentials_file, 'w') as f:
                json.dump(credential_data, f, indent=2)
            
            # Set restrictive permissions
            try:
                os.chmod(credentials_file, 0o600)
            except OSError:
                logger.warning(f"Could not set restrictive permissions on {credentials_file}")
            
            logger.info(f"Credentials stored successfully for service: {service_name}")
            
            # Log audit event
            audit_service.log_security_event(
                event_type=AuditEventType.CREDENTIALS_STORED,
                action="store_credentials",
                service_name=service_name,
                details={"credential_fields": list(credentials.keys())},
                severity=AuditSeverity.HIGH
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to store credentials for {service_name}: {str(e)}")
            return False
    
    def retrieve_credentials(self, service_name: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve and decrypt credentials for a service.
        
        Args:
            service_name: Name of the service
            
        Returns:
            Decrypted credentials dictionary or None if not found
        """
        try:
            credentials_file = self.credentials_dir / f"{service_name}.cred"
            
            if not credentials_file.exists():
                logger.warning(f"Credentials not found for service: {service_name}")
                return None
            
            # Load encrypted data
            with open(credentials_file, 'r') as f:
                credential_data = json.load(f)
            
            # Decrypt credentials
            decrypted_credentials = self.decrypt_data(
                credential_data["encrypted_data"], 
                return_type="dict"
            )
            
            logger.info(f"Credentials retrieved successfully for service: {service_name}")
            
            # Log audit event
            audit_service.log_security_event(
                event_type=AuditEventType.CREDENTIALS_ACCESSED,
                action="retrieve_credentials",
                service_name=service_name,
                severity=AuditSeverity.MEDIUM
            )
            
            return decrypted_credentials
            
        except Exception as e:
            logger.error(f"Failed to retrieve credentials for {service_name}: {str(e)}")
            return None
    
    def update_credentials(self, service_name: str, credentials: Dict[str, Any]) -> bool:
        """
        Update existing credentials for a service.
        
        Args:
            service_name: Name of the service
            credentials: New credential data
            
        Returns:
            True if credentials were updated successfully
        """
        try:
            credentials_file = self.credentials_dir / f"{service_name}.cred"
            
            # Load existing data to preserve metadata
            existing_data = {}
            if credentials_file.exists():
                with open(credentials_file, 'r') as f:
                    existing_data = json.load(f)
            
            # Encrypt new credentials
            encrypted_credentials = self.encrypt_data(credentials)
            
            # Update credential data
            credential_data = {
                "service_name": service_name,
                "encrypted_data": encrypted_credentials,
                "created_at": existing_data.get("created_at", self._get_current_timestamp()),
                "updated_at": self._get_current_timestamp()
            }
            
            with open(credentials_file, 'w') as f:
                json.dump(credential_data, f, indent=2)
            
            # Set restrictive permissions
            try:
                os.chmod(credentials_file, 0o600)
            except OSError:
                logger.warning(f"Could not set restrictive permissions on {credentials_file}")
            
            logger.info(f"Credentials updated successfully for service: {service_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update credentials for {service_name}: {str(e)}")
            return False
    
    def delete_credentials(self, service_name: str) -> bool:
        """
        Delete stored credentials for a service.
        
        Args:
            service_name: Name of the service
            
        Returns:
            True if credentials were deleted successfully
        """
        try:
            credentials_file = self.credentials_dir / f"{service_name}.cred"
            
            if credentials_file.exists():
                credentials_file.unlink()
                logger.info(f"Credentials deleted successfully for service: {service_name}")
                
                # Log audit event
                audit_service.log_security_event(
                    event_type=AuditEventType.CREDENTIALS_DELETED,
                    action="delete_credentials",
                    service_name=service_name,
                    severity=AuditSeverity.HIGH
                )
                
                return True
            else:
                logger.warning(f"Credentials not found for deletion: {service_name}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to delete credentials for {service_name}: {str(e)}")
            return False
    
    def list_stored_services(self) -> list[str]:
        """
        List all services that have stored credentials.
        
        Returns:
            List of service names
        """
        try:
            services = []
            for cred_file in self.credentials_dir.glob("*.cred"):
                service_name = cred_file.stem
                services.append(service_name)
            
            return sorted(services)
            
        except Exception as e:
            logger.error(f"Failed to list stored services: {str(e)}")
            return []
    
    def encrypt_sensitive_field(self, field_value: str) -> str:
        """
        Encrypt a single sensitive field value.
        
        Args:
            field_value: Value to encrypt
            
        Returns:
            Encrypted value with prefix to identify it as encrypted
        """
        if not field_value:
            return field_value
        
        try:
            encrypted_value = self.encrypt_data(field_value)
            return f"ENC:{encrypted_value}"
        except Exception as e:
            logger.error(f"Failed to encrypt field: {str(e)}")
            return field_value
    
    def decrypt_sensitive_field(self, field_value: str) -> str:
        """
        Decrypt a single sensitive field value.
        
        Args:
            field_value: Value to decrypt (should have ENC: prefix)
            
        Returns:
            Decrypted value or original value if not encrypted
        """
        if not field_value or not field_value.startswith("ENC:"):
            return field_value
        
        try:
            encrypted_value = field_value[4:]  # Remove "ENC:" prefix
            return self.decrypt_data(encrypted_value, return_type="string")
        except Exception as e:
            logger.error(f"Failed to decrypt field: {str(e)}")
            return field_value
    
    def generate_api_key(self, length: int = 32) -> str:
        """
        Generate a secure random API key.
        
        Args:
            length: Length of the API key in bytes
            
        Returns:
            Base64-encoded API key
        """
        try:
            random_bytes = os.urandom(length)
            api_key = base64.urlsafe_b64encode(random_bytes).decode('utf-8')
            return api_key.rstrip('=')  # Remove padding
        except Exception as e:
            logger.error(f"Failed to generate API key: {str(e)}")
            raise
    
    def hash_password(self, password: str, salt: Optional[bytes] = None) -> Dict[str, str]:
        """
        Hash a password using PBKDF2.
        
        Args:
            password: Password to hash
            salt: Optional salt (will generate if not provided)
            
        Returns:
            Dictionary containing hashed password and salt
        """
        try:
            if salt is None:
                salt = os.urandom(32)
            
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            
            password_hash = kdf.derive(password.encode('utf-8'))
            
            return {
                "hash": base64.b64encode(password_hash).decode('utf-8'),
                "salt": base64.b64encode(salt).decode('utf-8')
            }
            
        except Exception as e:
            logger.error(f"Failed to hash password: {str(e)}")
            raise
    
    def verify_password(self, password: str, stored_hash: str, stored_salt: str) -> bool:
        """
        Verify a password against stored hash and salt.
        
        Args:
            password: Password to verify
            stored_hash: Stored password hash
            stored_salt: Stored salt
            
        Returns:
            True if password is correct
        """
        try:
            salt = base64.b64decode(stored_salt.encode('utf-8'))
            expected_hash = base64.b64decode(stored_hash.encode('utf-8'))
            
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            
            try:
                kdf.verify(password.encode('utf-8'), expected_hash)
                return True
            except Exception:
                return False
                
        except Exception as e:
            logger.error(f"Failed to verify password: {str(e)}")
            return False
    
    def _get_current_timestamp(self) -> str:
        """Get current timestamp as ISO string."""
        from datetime import datetime
        return datetime.utcnow().isoformat()
    
    def rotate_encryption_key(self) -> bool:
        """
        Rotate the encryption key and re-encrypt all stored credentials.
        
        Returns:
            True if key rotation was successful
        """
        try:
            logger.info("Starting encryption key rotation")
            
            # Get list of all services
            services = self.list_stored_services()
            
            # Decrypt all credentials with old key
            decrypted_credentials = {}
            for service in services:
                credentials = self.retrieve_credentials(service)
                if credentials:
                    decrypted_credentials[service] = credentials
            
            # Generate new key
            old_key_file = self.credentials_dir / "encryption.key"
            backup_key_file = self.credentials_dir / f"encryption.key.backup.{self._get_current_timestamp()}"
            
            # Backup old key
            if old_key_file.exists():
                old_key_file.rename(backup_key_file)
            
            # Generate and initialize new key
            self._encryption_key = Fernet.generate_key()
            with open(old_key_file, 'wb') as f:
                f.write(self._encryption_key)
            
            try:
                os.chmod(old_key_file, 0o600)
            except OSError:
                logger.warning("Could not set restrictive permissions on new key file")
            
            self._fernet = Fernet(self._encryption_key)
            
            # Re-encrypt all credentials with new key
            for service, credentials in decrypted_credentials.items():
                self.store_credentials(service, credentials)
            
            logger.info(f"Encryption key rotation completed. Re-encrypted {len(decrypted_credentials)} credential sets")
            
            # Log audit event
            audit_service.log_security_event(
                event_type=AuditEventType.ENCRYPTION_KEY_ROTATED,
                action="rotate_encryption_key",
                details={"re_encrypted_services": len(decrypted_credentials)},
                severity=AuditSeverity.CRITICAL
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Encryption key rotation failed: {str(e)}")
            return False


# Global service instance
security_service = SecurityService()