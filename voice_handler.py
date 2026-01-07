import pyaudio
import wave
import threading
import whisper
import subprocess
import os
from pathlib import Path
import sys
import platform
import urllib.request

class VoiceHandler:
    """Handle voice input/output"""
    
    def __init__(self):
        # Audio settings
        self.CHUNK = 1024
        self.FORMAT = pyaudio.paInt16
        self.CHANNELS = 1
        self.RATE = 16000
        
        self.audio = pyaudio.PyAudio()
        
        # Whisper model
        print("🎤 Loading Whisper model...")
        self.whisper_model = whisper.load_model("base")
        print("✅ Whisper ready")
        
        # Recording state
        self.is_recording = False
        self.frames = []
        
        # TTS setup
        self.setup_piper()
    
    def setup_piper(self):
        """Setup Piper TTS with automatic voice download"""
        self.piper_available = False
        
        # Voice model path
        voices_dir = Path.home() / ".piper" / "voices"
        voices_dir.mkdir(parents=True, exist_ok=True)
        
        self.voice_model = voices_dir / "en_US-hfc_female-medium.onnx"
        self.voice_config = voices_dir / "en_US-hfc_female-medium.onnx.json"
        
        # Download voice if missing
        if not self.voice_model.exists() or not self.voice_config.exists():
            print("📥 Downloading Piper voice model...")
            try:
                base_url = "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/hfc_female/medium/"
                
                if not self.voice_model.exists():
                    print("  Downloading model (this may take a minute)...")
                    urllib.request.urlretrieve(
                        base_url + "en_US-hfc_female-medium.onnx",
                        self.voice_model
                    )
                    print(f"  ✅ Model saved")
                
                if not self.voice_config.exists():
                    print("  Downloading config...")
                    urllib.request.urlretrieve(
                        base_url + "en_US-hfc_female-medium.onnx.json",
                        self.voice_config
                    )
                    print(f"  ✅ Config saved")
                
                print("✅ Voice model downloaded")
            except Exception as e:
                print(f"❌ Failed to download voice: {e}")
                import traceback
                traceback.print_exc()
                return
        
        # Verify files
        if not self.voice_model.exists() or self.voice_model.stat().st_size == 0:
            print(f"❌ Voice model is missing or empty")
            return
        
        # Check if Piper is installed
        try:
            result = subprocess.run(
                [sys.executable, "-m", "piper", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            self.piper_cmd = [sys.executable, "-m", "piper"]
            print(f"✅ Piper found")
            self.piper_available = True
            
        except Exception as e:
            print(f"❌ Piper not available: {e}")
            return
        
        print(f"✅ Piper TTS ready")
    
    def start_recording(self):
        """Start recording audio"""
        if self.is_recording:
            return
        
        self.is_recording = True
        self.frames = []
        
        try:
            self.stream = self.audio.open(
                format=self.FORMAT,
                channels=self.CHANNELS,
                rate=self.RATE,
                input=True,
                frames_per_buffer=self.CHUNK
            )
            print("🎤 Recording...")
        except Exception as e:
            print(f"❌ Failed to start recording: {e}")
            self.is_recording = False
            return
        
        def record():
            while self.is_recording:
                try:
                    data = self.stream.read(self.CHUNK, exception_on_overflow=False)
                    self.frames.append(data)
                except Exception as e:
                    print(f"Recording error: {e}")
                    break
        
        threading.Thread(target=record, daemon=True).start()
    
    def stop_recording(self):
        """Stop recording and return audio file path"""
        if not self.is_recording:
            return None
        
        self.is_recording = False
        
        try:
            self.stream.stop_stream()
            self.stream.close()
        except Exception as e:
            print(f"Error stopping stream: {e}")
        
        if not self.frames:
            print("⚠️ No audio recorded")
            return None
        
        try:
            temp_file = "temp_recording.wav"
            wf = wave.open(temp_file, 'wb')
            wf.setnchannels(self.CHANNELS)
            wf.setsampwidth(self.audio.get_sample_size(self.FORMAT))
            wf.setframerate(self.RATE)
            wf.writeframes(b''.join(self.frames))
            wf.close()
            
            print(f"✅ Recording saved ({len(self.frames)} frames)")
            return temp_file
        except Exception as e:
            print(f"❌ Failed to save recording: {e}")
            return None
    
    def transcribe(self, audio_file):
        """Transcribe audio using Whisper"""
        if not audio_file or not os.path.exists(audio_file):
            print("⚠️ No audio file to transcribe")
            return None
        
        print("🎧 Transcribing...")
        
        try:
            result = self.whisper_model.transcribe(audio_file)
            
            # Handle both string and list returns
            text = result["text"]
            if isinstance(text, list):
                text = " ".join(text)
            
            text = text.strip()
            
            if text:
                print(f"📝 Transcribed: {text}")
                return text
            else:
                print("⚠️ Transcription was empty")
                return None
                
        except Exception as e:
            print(f"❌ Transcription error: {e}")
            import traceback
            traceback.print_exc()
            return None
        finally:
            try:
                os.remove(audio_file)
            except:
                pass
    
    def speak(self, text, callback=None):
        """Convert text to speech using Piper"""
        if not self.piper_available:
            print(f"🔇 TTS not available")
            if callback:
                callback()
            return
        
        if not text or not text.strip():
            print("⚠️ No text to speak")
            if callback:
                callback()
            return
        
        print(f"🗣️ Speaking: {text[:50]}...")
        
        def speak_thread():
            try:
                output_file = "temp_speech.wav"
                
                # Piper command
                cmd = self.piper_cmd + [
                    "--model", str(self.voice_model),
                    "--output_file", output_file
                ]
                
                print(f"Running: {' '.join(cmd)}")
                
                # Run Piper
                process = subprocess.Popen(
                    cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                
                stdout, stderr = process.communicate(input=text, timeout=30)
                
                if stderr:
                    print(f"Piper stderr: {stderr}")
                
                if process.returncode == 0 and os.path.exists(output_file):
                    file_size = os.path.getsize(output_file)
                    print(f"✅ Audio generated ({file_size} bytes)")
                    
                    if file_size > 0:
                        self.play_audio(output_file)
                    else:
                        print("❌ Generated audio file is empty")
                    
                    try:
                        os.remove(output_file)
                    except:
                        pass
                else:
                    print(f"❌ Piper failed (code {process.returncode})")
                
                if callback:
                    callback()
                    
            except subprocess.TimeoutExpired:
                print("❌ Piper timed out")
                if callback:
                    callback()
            except Exception as e:
                print(f"❌ TTS error: {e}")
                import traceback
                traceback.print_exc()
                if callback:
                    callback()
        
        threading.Thread(target=speak_thread, daemon=True).start()
    
    def play_audio(self, filename):
        """Play audio file"""
        try:
            print(f"🔊 Playing audio...")
            wf = wave.open(filename, 'rb')
            
            stream = self.audio.open(
                format=self.audio.get_format_from_width(wf.getsampwidth()),
                channels=wf.getnchannels(),
                rate=wf.getframerate(),
                output=True
            )
            
            data = wf.readframes(self.CHUNK)
            bytes_played = 0
            while data:
                stream.write(data)
                bytes_played += len(data)
                data = wf.readframes(self.CHUNK)
            
            stream.stop_stream()
            stream.close()
            wf.close()
            
            print(f"✅ Playback complete ({bytes_played} bytes)")
            
        except Exception as e:
            print(f"❌ Playback error: {e}")
            import traceback
            traceback.print_exc()
    
    def cleanup(self):
        """Clean up audio resources"""
        try:
            self.audio.terminate()
        except:
            pass