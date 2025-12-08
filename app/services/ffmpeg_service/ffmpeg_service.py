import subprocess
import os

class FFmpegService:
    def __init__(self):
        # Base is the directory of this file: app/services/ffmpeg_service/
        base = os.path.dirname(os.path.abspath(__file__))
        # Go up two levels to get to app/ then go to ffmpeg/bin/
        # So app/services/ffmpeg_service/ -> app/services/ -> app/ -> app/ffmpeg/bin/
        self.ffmpeg_path = os.path.abspath(os.path.join(base, "..", "..", "..", "ffmpeg", "bin", "ffmpeg.exe"))
        self.ffprobe_path = os.path.abspath(os.path.join(base, "..", "..", "..", "ffmpeg", "bin", "ffprobe.exe"))

    def run(self, args: list):
        cmd = [self.ffmpeg_path] + args
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.stdout, result.stderr

    def run_with_check(self, args: list):
        """Run FFmpeg command and raise exception if it fails"""
        cmd = [self.ffmpeg_path] + args
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise Exception(f"FFmpeg command failed with return code {result.returncode}: {result.stderr}")

        return result.stdout, result.stderr


ffmpeg_service = FFmpegService()
