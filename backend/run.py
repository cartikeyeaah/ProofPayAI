"""Local entry point: load private root .env without replacing exported settings."""
from pathlib import Path
from dotenv import load_dotenv
import uvicorn


def main():
    load_dotenv(Path(__file__).resolve().parents[1] / '.env', override=False)
    uvicorn.run('backend.app.main:app', host='127.0.0.1', port=8000, workers=1)

if __name__ == '__main__':
    main()
