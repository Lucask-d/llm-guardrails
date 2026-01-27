import os

def load_env_file(path=".env"):
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())
    except FileNotFoundError:
        pass

load_env_file()
print("CWD:", os.getcwd())
print("ENV FOUND:", os.path.exists(".env"))

print("ENV FOUND:", os.path.exists(".env"))

api_key = os.environ.get("MISTRAL_API_KEY")
if not api_key:
    print("not got")
