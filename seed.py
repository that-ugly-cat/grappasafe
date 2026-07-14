"""
Create the initial admin user.
Usage: python seed.py
"""
import os
from dotenv import load_dotenv
load_dotenv()

from db import init_db, create_user, get_user_by_username
from auth import hash_password

init_db()

username = os.getenv("ADMIN_USER", "admin")
password = os.getenv("ADMIN_PASS", "changeme")
nome     = os.getenv("ADMIN_NOME", "Admin")
cognome  = os.getenv("ADMIN_COGNOME", "GrappaSafe")

if get_user_by_username(username):
    print(f"User '{username}' already exists.")
else:
    create_user(username, hash_password(password), nome, cognome, role="admin")
    print(f"Admin user '{username}' created.")
