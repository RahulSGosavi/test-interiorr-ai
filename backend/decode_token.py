import os
from jose import jwt
from dotenv import load_dotenv
load_dotenv('.env')
token='eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOjEsImV4cCI6MTc2NTExMzU1Mn0.IOlvkFxRa5ckGnoYJyneqbCz-1ubxAP_SsYZhmHNjhk'
print(jwt.get_unverified_claims(token))
secret_key = os.getenv('SECRET_KEY')
if secret_key:
    print(jwt.decode(token, secret_key, algorithms=['HS256']))
else:
    print("SECRET_KEY not found in environment")
