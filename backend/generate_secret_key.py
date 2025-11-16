#!/usr/bin/env python3
"""
Generate a secure SECRET_KEY for JWT token signing.
Run this script to generate a new secret key for your .env file.
"""
import secrets

def generate_secret_key():
    """Generate a secure random secret key."""
    return secrets.token_urlsafe(32)

if __name__ == "__main__":
    key = generate_secret_key()
    print("=" * 60)
    print("Generated SECRET_KEY:")
    print("=" * 60)
    print(key)
    print("=" * 60)
    print("\nAdd this to your .env file:")
    print(f"SECRET_KEY={key}")
    print("\n⚠️  Keep this key secret and never commit it to version control!")

