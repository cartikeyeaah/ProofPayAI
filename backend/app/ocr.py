"""Optional local OCR adapter using existing engine OCRReader interface."""
import os
import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from ai_engine.extraction.parser import DocumentError, tesseract_image_reader

def available():
    if os.getenv('OCR_ENABLED', 'false').lower() != 'true': return False
    try:
        import pytesseract
        import PIL
    except ImportError: return False
    return bool(shutil.which('tesseract') and shutil.which('pdftoppm'))

def local_ocr(data, media_type):
    if media_type != 'application/pdf': return tesseract_image_reader(data, media_type)
    with TemporaryDirectory(prefix='proofpay-ocr-') as folder:
        source = Path(folder) / 'input.pdf'
        source.write_bytes(data)
        source.chmod(0o600)
        try:
            subprocess.run(['pdftoppm','-png','-r','150','-scale-to','2500',str(source),str(Path(folder)/'page')], check=True, timeout=20, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            pages = sorted(Path(folder).glob('page-*.png'), key=lambda p:int(p.stem.split('-')[-1]))
            return [tesseract_image_reader(p.read_bytes(),'image/png')[0] for p in pages]
        except (subprocess.SubprocessError, OSError):
            raise DocumentError('OCR_FAILED')

def configured_pipeline(payload):
    from ai_engine import run_pipeline
    return run_pipeline(payload, ocr=local_ocr if available() else None)
