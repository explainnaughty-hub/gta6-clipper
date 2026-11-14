import os
import sys
import wave
import subprocess
import numpy as np

def analyze_audio_peaks(clean_wav_file, num_clips=3, clip_duration=35):
    """Audio data scan kar ke top loudest/craziest moments nikalta hai."""
    print("🔍 Highlights scan ho rahi hain...")
    
    with wave.open(clean_wav_file, "rb") as wf:
        framerate = wf.getframerate()
        n_frames = wf.getnframes()
        raw_data = wf.readframes(n_frames)
        audio_data = np.frombuffer(raw_data, dtype=np.int16)
            
    chunk_size = framerate  # 1 second ke chunks
    total_seconds = len(audio_data) // chunk_size

    if total_seconds < 10:
        print("❌ Video bohot choti hai!")
        sys.exit(1)
    
    # Har second ka volume energy calculate karna
    energy = []
    for i in range(total_seconds):
        chunk = audio_data[i * chunk_size : (i + 1) * chunk_size]
        rms = np.sqrt(np.mean(chunk.astype(float)**2)) if len(chunk) > 0 else 0
        energy.append(rms)
        
    energy = np.array(energy)
    
    # Top peaks find karna (kam az kam 60 second door hon aik doosre se)
    peaks = []
    min_distance = 60
    sorted_indices = np.argsort(energy)[::-1]
    
    for idx in sorted_indices:
        if len(peaks) >= num_clips:
            break
        if all(abs(idx - p) > min_distance for p in peaks):
            peaks.append(idx)
            
    # Agar video silent ho toh evenly clips cut karein
    if len(peaks) == 0:
        peaks = [int(total_seconds * (i + 1) / (num_clips + 1)) for i in range(num_clips)]

    highlights = []
    for p in sorted(peaks):
        start = max(0, p - 12)  # Action se 12s pehle se shuru
        end = min(total_seconds, start + clip_duration)
        highlights.append((start, end))
        print(f"🎯 Highlight Found: {start}s se {end}s tak")
        
    return highlights

def main():
    if len(sys.argv) < 2:
        print("❌ Video URL missing hai!")
        sys.exit(1)

    video_url = sys.argv[1]
    num_clips = int(sys.argv[2]) if len(sys.argv) > 2 else 3

    os.makedirs("clips", exist_ok=True)
    os.makedirs("temp", exist_ok=True)

    print("📥 Stream ka audio fetch ho raha hai...")
    raw_audio = "temp/raw_audio.wav"
    clean_audio = "temp/clean_audio.wav"

    # Cookies check karna
    cookie_args = []
    if os.path.exists("cookies.txt") and os.path.getsize("cookies.txt") > 20:
        print("🍪 Authenticated YouTube Cookies use ho rahi hain...")
        cookie_args = ["--cookies", "cookies.txt"]

    # Step 1: Audio download with explicit audio format
    cmd_audio = [
        "yt-dlp",
        "-f", "ba/b",
        "-x", "--audio-format", "wav",
        "--force-overwrites",
        "-o", raw_audio
    ] + cookie_args + [video_url]
    
    subprocess.run(cmd_audio, check=True)

    # Step 2: Audio ko standard 16kHz Mono banana
    subprocess.run([
        "ffmpeg", "-y", "-i", raw_audio,
        "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le",
        clean_audio
    ], check=True)

    # Step 3: Highlights calculate karna
    highlights = analyze_audio_peaks(clean_audio, num_clips=num_clips)

    # Step 4: Har highlight ko 9:16 vertical video mein convert karna
    blur_filter = (
        "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,gblur=sigma=20[bg];"
        "[0:v]scale=1080:-2[fg];"
        "[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1"
    )

    for i, (start, end) in enumerate(highlights):
        raw_clip = f"temp/raw_{i+1}.mp4"
        final_clip = f"clips/gta6_clip_{i+1}.mp4"

        print(f"\n✂️ Generating Clip {i+1} ({start}s - {end}s)...")
        
        # Download targeted clip section
        cmd_clip = [
            "yt-dlp",
            "--download-sections", f"*{start}-{end}",
            "--force-keyframes-at-cuts",
            "-f", "bv*+ba/b",
            "--merge-output-format", "mp4",
            "--force-overwrites",
            "-o", raw_clip
        ] + cookie_args + [video_url]

        subprocess.run(cmd_clip, check=True)

        # Convert to 9:16 vertical with blurred background
        subprocess.run([
            "ffmpeg", "-y", "-i", raw_clip,
            "-filter_complex", blur_filter,
            "-c:v", "libx264", "-preset", "fast", "-crf", "22",
            "-c:a", "aac", "-b:a", "192k",
            final_clip
        ], check=True)

    print("\n✅ Tamam clips ready ho chuki hain!")

if __name__ == "__main__":
    main()
