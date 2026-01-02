import os
import sys
import subprocess
import urllib.request
from typing import List

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, HttpUrl, field_validator

app = FastAPI(title="Japanese Lyrics Alignment Service")


class AlignmentRequest(BaseModel):
    audio_url: HttpUrl
    lyrics: List[str]
    
    @field_validator('lyrics')
    @classmethod
    def validate_lyrics(cls, v):
        """Validate that lyrics is a list of individual lines, not a multiline string."""
        if not isinstance(v, list):
            raise ValueError("lyrics must be a list of strings")
        if not v:
            raise ValueError("lyrics cannot be empty")
        for i, line in enumerate(v):
            if not isinstance(line, str):
                raise ValueError(f"lyrics[{i}] must be a string, got {type(line).__name__}")
            # Check if it looks like a multiline string (contains newlines)
            if '\n' in line:
                raise ValueError(
                    f"lyrics[{i}] appears to be a multiline string. "
                    "Each item in lyrics should be a single line. "
                    "Split multiline strings into separate list items."
                )
        return v


class AlignmentResult(BaseModel):
    line_index: int
    text: str
    start: float
    end: float


def download_audio(url: str, output_path: str) -> None:
    """Download audio file from URL."""
    try:
        urllib.request.urlretrieve(url, output_path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to download audio: {str(e)}")


def convert_audio_to_wav(input_path: str, output_path: str) -> None:
    """
    Convert audio to mono 16kHz WAV using ffmpeg.
    
    Why ffmpeg is required:
    - Aeneas requires audio in a specific format (mono, 16kHz WAV)
    - Input audio may be in various formats (MP3, WAV, etc.) and sample rates
    - ffmpeg handles format conversion and resampling reliably
    """
    try:
        cmd = [
            "ffmpeg",
            "-i", input_path,
            "-ac", "1",  # mono
            "-ar", "16000",  # 16kHz
            "-y",  # overwrite output
            output_path
        ]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
    except subprocess.CalledProcessError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Audio conversion failed: {e.stderr}"
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=500,
            detail="ffmpeg not found. Please install ffmpeg."
        )


def write_lyrics_file(lyrics: List[str], output_path: str) -> None:
    """Write lyrics to a text file, one line per lyric."""
    if not lyrics:
        raise HTTPException(status_code=400, detail="Lyrics array cannot be empty")
    
    with open(output_path, "w", encoding="utf-8") as f:
        for line in lyrics:
            f.write(line.strip() + "\n")


def run_aeneas_alignment(audio_path: str, text_path: str, output_path: str) -> None:
    """
    Run Aeneas forced alignment for Japanese text.
    
    Why espeak-ng is required:
    - Aeneas uses a TTS (text-to-speech) engine to generate reference audio
    - The reference audio is compared with the input audio to find alignments
    - espeak-ng provides Japanese TTS support that Aeneas needs
    - Without espeak-ng, Aeneas cannot generate the reference audio for alignment
    
    Why Aeneas cannot run without system dependencies:
    - Aeneas requires espeak-ng to be installed as a system package (not a Python package)
    - The TTS engine must be accessible via system PATH
    - Python bindings alone are not sufficient - the underlying C libraries are needed
    """
    try:
        # Use sys.executable to ensure we use the same Python interpreter
        # This is critical - using "python" may point to a different interpreter
        # that doesn't have aeneas installed
        cmd = [
            sys.executable, "-m", "aeneas.tools.execute_task",
            audio_path,
            text_path,
            "task_language=jpn|os_task_file_format=json|is_text_type=plain",
            output_path
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
    except subprocess.CalledProcessError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Aeneas alignment failed: {e.stderr}"
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=500,
            detail="Aeneas not found. Please install aeneas."
        )


def parse_aeneas_output(output_path: str, lyrics: List[str]) -> List[AlignmentResult]:
    """Parse Aeneas JSON output and return alignment results."""
    import json
    
    try:
        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to parse Aeneas output: {str(e)}"
        )
    
    results = []
    fragments = data.get("fragments", [])
    
    if len(fragments) != len(lyrics):
        raise HTTPException(
            status_code=500,
            detail=f"Alignment mismatch: {len(fragments)} fragments for {len(lyrics)} lyrics"
        )
    
    for idx, fragment in enumerate(fragments):
        # Try fragment-level begin/end first
        if "begin" in fragment and "end" in fragment:
            start = float(fragment["begin"])
            end = float(fragment["end"])
        else:
            # Fall back to lines
            lines = fragment.get("lines", [])
            if not lines:
                raise HTTPException(
                    status_code=500,
                    detail=f"Fragment {idx + 1} has no timing information"
                )
            first_line = lines[0]
            last_line = lines[-1]
            start = float(first_line.get("begin", 0))
            end = float(last_line.get("end", 0))
        
        results.append(AlignmentResult(
            line_index=idx + 1,  # 1-based index
            text=lyrics[idx],
            start=start,
            end=end
        ))
    
    return results


@app.post("/align", response_model=List[AlignmentResult])
async def align_lyrics(request: AlignmentRequest):
    """
    Perform forced alignment of Japanese song lyrics to audio.
    
    - Downloads audio from the provided URL
    - Converts to mono 16kHz WAV
    - Aligns lyrics using Aeneas
    - Returns timing information for each lyric line
    """
    # Use /tmp directory for temporary files
    temp_dir = "/tmp"
    
    # Generate unique filenames
    import uuid
    unique_id = str(uuid.uuid4())
    
    downloaded_audio = os.path.join(temp_dir, f"audio_{unique_id}")
    converted_audio = os.path.join(temp_dir, f"converted_{unique_id}.wav")
    lyrics_file = os.path.join(temp_dir, f"lyrics_{unique_id}.txt")
    alignment_output = os.path.join(temp_dir, f"alignment_{unique_id}.json")
    
    try:
        # Download audio
        download_audio(str(request.audio_url), downloaded_audio)
        
        # Convert to mono 16kHz WAV
        convert_audio_to_wav(downloaded_audio, converted_audio)
        
        # Write lyrics to file
        write_lyrics_file(request.lyrics, lyrics_file)
        
        # Run Aeneas alignment
        run_aeneas_alignment(converted_audio, lyrics_file, alignment_output)
        
        # Parse results
        results = parse_aeneas_output(alignment_output, request.lyrics)
        
        return results
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error: {str(e)}"
        )
    finally:
        # Clean up temporary files
        for file_path in [downloaded_audio, converted_audio, lyrics_file, alignment_output]:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception:
                pass  # Ignore cleanup errors


def check_dependencies():
    """
    Verify all required dependencies are available at startup.
    This prevents runtime errors and provides clear feedback.
    """
    errors = []
    
    # Check ffmpeg
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode != 0:
            errors.append("ffmpeg is installed but returned an error")
    except FileNotFoundError:
        errors.append("ffmpeg not found. Install with: brew install ffmpeg (macOS) or apt-get install ffmpeg (Linux)")
    except subprocess.TimeoutExpired:
        errors.append("ffmpeg check timed out")
    
    # Check espeak-ng
    try:
        result = subprocess.run(
            ["espeak-ng", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode != 0:
            errors.append("espeak-ng is installed but returned an error")
    except FileNotFoundError:
        errors.append("espeak-ng not found. Install with: brew install espeak-ng (macOS) or apt-get install espeak-ng (Linux)")
    except subprocess.TimeoutExpired:
        errors.append("espeak-ng check timed out")
    
    # Check aeneas Python module
    try:
        import aeneas
        # Try to import the execute_task module specifically
        from aeneas.tools import execute_task
    except ImportError as e:
        errors.append(f"aeneas Python module not found. Install with: pip3 install aeneas. Error: {str(e)}")
    
    # If any errors, print them and raise an exception
    if errors:
        error_msg = "\n".join([f"  - {error}" for error in errors])
        full_msg = (
            "\n" + "=" * 60 + "\n"
            "DEPENDENCY CHECK FAILED\n"
            "The following required dependencies are missing or broken:\n\n"
            f"{error_msg}\n\n"
            "Please install all dependencies before starting the server.\n"
            "=" * 60 + "\n"
        )
        print(full_msg, file=sys.stderr)
        raise RuntimeError("Missing required dependencies. See error messages above.")
    
    print("✓ All dependencies verified: ffmpeg, espeak-ng, aeneas")


@app.on_event("startup")
async def startup_event():
    """Run dependency checks when the server starts."""
    check_dependencies()


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "service": "Japanese Lyrics Alignment"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

