"""
Security Utilities Module, a part of ATM-VEND system

This module provides utility functions for handling password security, including hashing,
verification, and token IV generation. It is designed to ensure robust and consistent
implementation of security features across the system.

Author: Vladimir Perekladov
Email: gleero@gmail.com
"""

import uuid

import base58
from password_generator import PasswordGenerator
from pwdlib import PasswordHash


password_hash = PasswordHash.recommended()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Validate plaintext password against hashed password
    :param plain_password: plaintext password
    :param hashed_password: hashed password
    :return: result of verifying password
    """
    return password_hash.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """
    Generate hashed password
    :param password: plaintext password
    :return: Hashed password
    """
    return password_hash.hash(password)


def generate_password(size: int) -> str:
    """
    Generate a new password
    :param size: result length
    :return: password
    """
    pgen = PasswordGenerator()
    pgen.minlen = size
    pgen.maxlen = size
    return pgen.generate()


def generate_unique_index() -> str:
    """
    Generate a new random string index
    :return: string
    """
    unique_uuid = uuid.uuid4()
    result = base58.b58encode(unique_uuid.bytes)
    return result.decode("utf-8")[:22].ljust(22, "0")
