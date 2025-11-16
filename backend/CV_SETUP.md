# Computer Vision & Multilingual NLP Setup

## Required Dependencies

### Python Packages (already in requirements.txt)
- `pytesseract>=0.3.10` - OCR for text extraction
- `opencv-python>=4.5.0` - Computer vision for drawing analysis
- `langdetect>=1.0.9` - Language detection
- `googletrans==4.0.0rc1` - Translation service
- `pillow>=9.0.0` - Image processing (already installed)

### System Requirements

#### Tesseract OCR (Required for image processing)
**Windows:**
1. Download installer from: https://github.com/UB-Mannheim/tesseract/wiki
2. Install to default location: `C:\Program Files\Tesseract-OCR`
3. Add to PATH or set environment variable:
   ```powershell
   $env:TESSDATA_PREFIX = "C:\Program Files\Tesseract-OCR\tessdata"
   ```

**Linux (Ubuntu/Debian):**
```bash
sudo apt-get update
sudo apt-get install tesseract-ocr
```

**macOS:**
```bash
brew install tesseract
```

#### OpenCV (Optional, for advanced drawing analysis)
- Usually installed automatically with `opencv-python`
- If issues occur, install system libraries:
  - Linux: `sudo apt-get install libopencv-dev`
  - macOS: `brew install opencv`

## Installation

```bash
pip install -r requirements.txt
```

## Verification

Test if Tesseract is available:
```python
import pytesseract
print(pytesseract.get_tesseract_version())
```

## Performance Notes

- **File Caching**: Files are cached in memory (5 min TTL) - first query reads file, subsequent queries are instant
- **Parallel Processing**: Bulk questions are processed in parallel using async/await - all AI API calls happen simultaneously
- **Expected Speed**: 
  - Single question: 1-3 seconds
  - 5 bulk questions (parallel): 2-4 seconds (instead of 10-15 seconds sequential)

