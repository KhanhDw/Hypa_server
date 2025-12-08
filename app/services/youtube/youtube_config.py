"""
Configuration for YouTube download options to handle warnings and ensure compatibility
"""

class YouTubeConfig:
    """
    Configuration class for yt-dlp options to handle JavaScript runtime requirements
    and SABR streaming issues mentioned in the warnings.
    """
    
    @staticmethod
    def get_base_options():
        """
        Get base options for yt-dlp to handle YouTube's JavaScript runtime requirement
        and SABR streaming issues.
        """
        return {
            "extractor_args": {"youtube": {"player_client": "android"}},
            "quiet": True,
            "noplaylist": True,
        }
    
    @staticmethod
    def get_video_options(quality="720p"):
        """
        Get options for video-only downloads
        """
        base_opts = YouTubeConfig.get_base_options()
        base_opts.update({
            "format": f"bestvideo[height<={quality.replace('p','')}]",
            "outtmpl": "downloads/%(id)s_video_only.%(ext)s",
        })
        return base_opts
    
    @staticmethod
    def get_audio_options():
        """
        Get options for audio-only downloads
        """
        base_opts = YouTubeConfig.get_base_options()
        base_opts.update({
            "format": "bestaudio/best",
            "outtmpl": "downloads/%(id)s_audio.%(ext)s",
        })
        return base_opts
    
    @staticmethod
    def get_merged_video_options(quality="720p"):
        """
        Get options for best video when merging with audio
        """
        base_opts = YouTubeConfig.get_base_options()
        base_opts.update({
            "format": f"bestvideo[height<={quality.replace('p','')}]",
            "outtmpl": "downloads/%(id)s_video.%(ext)s",
        })
        return base_opts
    
    @staticmethod
    def get_metadata_options():
        """
        Get options for fetching metadata only
        """
        base_opts = YouTubeConfig.get_base_options()
        base_opts.update({
            "quiet": True,
            "skip_download": True,
            "forcejson": True,
        })
        return base_opts
    
    @staticmethod
    def get_audio_extraction_options(audio_format="mp3"):
        """
        Get options for extracting audio in specific format
        """
        base_opts = YouTubeConfig.get_base_options()
        base_opts.update({
            "format": "bestaudio/best",
            "outtmpl": "downloads/%(title)s.%(ext)s",
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": audio_format,
                }
            ],
        })
        return base_opts