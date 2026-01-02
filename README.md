# Japanese Lyrics Alignment Service

A minimal FastAPI service that performs forced alignment of Japanese song lyrics to audio using Aeneas.

## Features

- POST `/align` endpoint for forced alignment
- Downloads audio from public URLs
- Converts audio to mono 16kHz WAV format
- Aligns Japanese lyrics to audio timestamps
- Returns JSON with line-by-line timing information

## System Requirements

The following system packages must be installed:

- **ffmpeg** - For audio conversion (converts input audio to mono 16kHz WAV format required by Aeneas)
- **espeak-ng** - Text-to-speech engine required by Aeneas (generates reference audio for alignment)
- **aeneas** - Python package for forced alignment (installed via pip)

**Note:** The service performs startup checks and will fail to start if any dependency is missing.

### Installation on macOS

```bash
brew install ffmpeg espeak-ng
```

### Installation on Ubuntu/Debian

```bash
sudo apt-get update
sudo apt-get install -y ffmpeg espeak-ng
```

## Python Dependencies

Install Python dependencies:

**On macOS (use pip3 or python3 -m pip):**
```bash
pip3 install -r requirements.txt
```

**Or alternatively:**
```bash
python3 -m pip install -r requirements.txt
```

**On Linux/other systems:**
```bash
pip install -r requirements.txt
```

## Running Locally

Start the service:

**On macOS:**
```bash
python3 main.py
```

**On Linux/other systems:**
```bash
python main.py
```

Or using uvicorn directly:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

The service will be available at `http://localhost:8000`

**Startup Checks:**
When the server starts, it automatically verifies:
- ✓ ffmpeg is available
- ✓ espeak-ng is available  
- ✓ aeneas Python module is importable

If any dependency is missing, the server will print clear error messages and exit.

## Testing with Swagger UI

The easiest way to test the service is using the built-in Swagger UI:

1. Start the server: `python3 main.py`
2. Open your browser and go to: `http://127.0.0.1:8000/docs`
3. You'll see the interactive API documentation
4. Click on `POST /align` to expand it
5. Click "Try it out"
6. Enter your request body in the JSON format below
7. Click "Execute"

**Example Request Body for Swagger UI:**

```json
{
  "audio_url": "https://example.com/your-song.mp3",
  "lyrics": [
    "さぁ、怖くはない",
    "もう迷わないで",
    "心のままに"
  ]
}
```

**Important:** 
- `audio_url` must be a publicly accessible URL (http:// or https://)
- `lyrics` must be an array of strings, where each string is a single line
- Do NOT use multiline strings in the lyrics array - each line should be a separate array item

## API Usage

### Endpoint: POST `/align`

**Request Body:**

```json
{
  "audio_url": "https://example.com/song.mp3",
  "lyrics": [
    "さぁ、怖くはない",
    "もう迷わないで",
    "心のままに"
  ]
}
```

**Response:**

```json
[
  {
    "line_index": 1,
    "text": "さぁ、怖くはない",
    "start": 0.52,
    "end": 2.01
  },
  {
    "line_index": 2,
    "text": "もう迷わないで",
    "start": 2.15,
    "end": 3.89
  },
  {
    "line_index": 3,
    "text": "心のままに",
    "start": 4.02,
    "end": 5.45
  }
]
```

### Example cURL Request

```bash
curl -X POST "http://localhost:8000/align" \
  -H "Content-Type: application/json" \
  -d '{
    "audio_url": "https://example.com/song.mp3",
    "lyrics": [
      "さぁ、怖くはない",
      "もう迷わないで"
    ]
  }'
```

## Deployment

### Render.com

1. Create a new Web Service
2. Connect your repository
3. Build command: `pip install -r requirements.txt`
4. Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Add system packages in the build settings (ffmpeg, espeak-ng)

### Railway

1. Create a new project
2. Connect your repository
3. Railway will auto-detect Python
4. Add system packages via `nixpacks.toml` or build script
5. Set start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`

### System Packages for Cloud Deployment

For cloud platforms, you may need to install system packages via:

- **Render**: Use a build script or Dockerfile (if needed)
- **Railway**: Use `nixpacks.toml` or build hooks
- **Heroku**: Use `aptfile` or buildpacks

Example build script for installing system packages:

```bash
#!/bin/bash
apt-get update
apt-get install -y ffmpeg espeak-ng
```

## Error Handling

The service handles the following error cases:

- Invalid audio URL (400)
- Empty lyrics array (400)
- Lyrics not a list of strings (400)
- Multiline strings in lyrics array (400) - each item must be a single line
- Audio download failure (400)
- ffmpeg conversion failure (500)
- Aeneas alignment failure (500)
- Missing system dependencies (500) - checked at startup

**Startup Validation:**
If the server fails to start, check the error messages. Common issues:
- Missing `ffmpeg`: Install with `brew install ffmpeg` (macOS) or `apt-get install ffmpeg` (Linux)
- Missing `espeak-ng`: Install with `brew install espeak-ng` (macOS) or `apt-get install espeak-ng` (Linux)
- Missing `aeneas` Python module: Install with `pip3 install aeneas`

## Notes

- Temporary files are automatically cleaned up after each request
- Audio files are converted to mono 16kHz WAV before alignment
- The service assumes Japanese text (task_language=jpn)
- Line indexes in the response are 1-based

