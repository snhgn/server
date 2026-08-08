import bcrypt, secrets
print("JWT_SECRET=" + secrets.token_hex(32))
print("HASH=" + bcrypt.hashpw(b"changeme123", bcrypt.gensalt()).decode())
