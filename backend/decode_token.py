import os
from jose import jwt
from dotenv import load_dotenv
load_dotenv('.env')
token='eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOjEsImV4cCI6MTc2NTExMzU1Mn0.IOlvkFxRa5ckGnoYJyneqbCz-1ubxAP_SsYZhmHNjhk'
print(jwt.get_unverified_claims(token))
print(jwt.decode(token, os.getenv('SECRET_KEY'), algorithms=['HS256']))
