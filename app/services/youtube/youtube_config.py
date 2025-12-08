"""
Enhanced configuration for yt-dlp to avoid JavaScript runtime warnings,
reduce SABR-related issues, and improve overall YouTube download stability.
"""

class YouTubeConfig:

    @staticmethod
    def get_base_options():
        """
        Base yt-dlp options to:
        - Avoid JavaScript runtime warnings
        - Improve SABR streaming behavior
        - Reduce unnecessary webpage parsing
        - Increase stability for all YouTube extractions
        """

        extractor_args = {
            "youtube": {
                # Use multiple player clients for better compatibility
                "player_client": ["android", "web", "ios"],

                # Skip webpage extraction for faster processing
                "player_skip": ["webpage", "js"],

                # Fix SABR issues (throttling / slow stream)
                "sabr": "no_mpeg",

                # Force using InnerTube API for higher reliability
                "force_innertube": True,

                # Additional extractor options for better performance
                "include_live_chat": False,  # Exclude live chat to reduce data
            }
        }

        return {
            "extractor_args": extractor_args,
            "quiet": True,
            "no_warnings": False,  # Keep warnings to identify potential issues
            "ignore_warnings": True,  # But ignore non-critical warnings
            "noplaylist": True,
            "nocheckcertificate": True,
            "prefer_ffmpeg": True,
            "encoding": "utf-8",
            # Additional options for better performance and quality
            "extractaudio": False,
            "audioquality": "0",
            "retries": 20,
            "fragment_retries": 20,
            "file_access_retries": 15,
            "buffersize": 1024 * 1024,  # 1MB buffer
            "http_chunk_size": 10485760,  # 10MB chunk size for better performance
            "extractor_retries": 5,
            "sleep_interval_requests": 1,  # Small delay between requests
            "max_sleep_interval": 3,
            "concurrent_fragment_downloads": 3,  # Download multiple fragments concurrently
            # Additional performance options
            "skip_unavailable_fragments": True,
            "keep_fragments": False,
            "postprocessor_args": {
                'ffmpeg': ['-threads', '2']  # Use 2 threads for ffmpeg processing
            },
            "compat_opts": ["no-live-chat"],  # Skip live chat for faster processing
        }

    # ---------------------------------------------------------
    # VIDEO ONLY
    # ---------------------------------------------------------
    @staticmethod
    def get_video_options(quality="720p"):
        base_opts = YouTubeConfig.get_base_options()
        height = quality.replace('p','')
        base_opts.update({
            "format": (
                f"bestvideo[height<={height}][ext=mp4]+bestaudio[ext=m4a]/"
                f"bestvideo[height<={height}][ext=webm]+bestaudio[ext=webm]/"
                f"bestvideo[height<={height}][ext=mp4]/"
                f"bestvideo[height<={height}][ext=webm]/"
                f"best[height<={height}]"
            ),
            "outtmpl": "downloads/%(id)s_video_only.%(ext)s",
        })
        return base_opts

    # ---------------------------------------------------------
    # AUDIO ONLY
    # ---------------------------------------------------------
    @staticmethod
    def get_audio_options():
        base_opts = YouTubeConfig.get_base_options()
        base_opts.update({
            "format": "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio",
            "outtmpl": "downloads/%(id)s_audio.%(ext)s",
        })
        return base_opts

    # ---------------------------------------------------------
    # MERGED VIDEO
    # ---------------------------------------------------------
    @staticmethod
    def get_merged_video_options(quality="720p"):
        base_opts = YouTubeConfig.get_base_options()
        height = quality.replace('p','')
        base_opts.update({
            "format": (
                f"bestvideo[height<={height}][ext=mp4]+bestaudio[ext=m4a]/"
                f"bestvideo[height<={height}][ext=webm]+bestaudio[ext=webm]/"
                f"best[height<={height}][ext=mp4]/"
                f"best[height<={height}][ext=webm]/"
                f"best[height<={height}]/"
                f"best"
            ),
            "outtmpl": "downloads/%(id)s_video.%(ext)s",
            "merge_output_format": "mp4",
        })
        return base_opts

    # ---------------------------------------------------------
    # METADATA ONLY
    # ---------------------------------------------------------
    @staticmethod
    def get_metadata_options():
        base_opts = YouTubeConfig.get_base_options()
        base_opts.update({
            "skip_download": True,
            "forcejson": True,
        })
        return base_opts

    # ---------------------------------------------------------
    # AUDIO EXTRACTION (MP3, WAV…)
    # ---------------------------------------------------------
    @staticmethod
    def get_audio_extraction_options(audio_format="mp3"):
        base_opts = YouTubeConfig.get_base_options()
        # Ensure we only download audio, with fallback to lowest quality video if needed
        base_opts.update({
            "format": (
                "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best"  # Prefer audio-only formats
            ),
            "outtmpl": "downloads/%(title)s.%(ext)s",
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": audio_format,
                    "preferredquality": YouTubeConfig._get_audio_quality(audio_format),
                }
            ],
            "postprocessor_args": {
                'FFmpegExtractAudio': YouTubeConfig._get_audio_encoder_args(audio_format)
            },
            # Skip video download when possible
            "extractaudio": True,  # This forces audio extraction
        })
        return base_opts

    @staticmethod
    def _get_audio_quality(audio_format: str) -> str:
        """Get appropriate quality setting based on audio format"""
        quality_map = {
            'mp3': '0',      # Highest quality MP3 (320k)
            'm4a': '0',      # Lossless/M4A
            'aac': '0',      # Highest quality AAC
            'flac': '0',     # Lossless FLAC
            'opus': '0',     # Highest quality Opus
            'vorbis': '0',   # Highest quality Vorbis
            'wav': '0',      # WAV is lossless by nature
        }
        return quality_map.get(audio_format.lower(), '0')

    @staticmethod
    def _get_audio_encoder_args(audio_format: str) -> list:
        """Get appropriate encoder arguments based on audio format"""
        encoder_args = {
            'mp3': ['-b:a', '320k'],          # High quality MP3
            'm4a': ['-q:a', '0'],             # High quality M4A
            'aac': ['-b:a', '320k'],          # High quality AAC
            'flac': ['-compression_level', '12'],  # Highest compression for FLAC
            'opus': ['-b:a', '320k'],         # High quality Opus
            'vorbis': ['-q:a', '10'],         # Highest quality Vorbis
            'wav': [],                        # WAV doesn't need bitrate settings
        }
        return encoder_args.get(audio_format.lower(), ['-b:a', '320k'])

    # ---------------------------------------------------------
    # LOWEST QUALITY VIDEO (for audio extraction fallback)
    # ---------------------------------------------------------
    @staticmethod
    def get_lowest_quality_video_options():
        """
        Get options to download the lowest quality video possible for audio extraction fallback.
        This ensures minimal data usage when audio-only download is not available.
        """
        base_opts = YouTubeConfig.get_base_options()
        base_opts.update({
            "format": (
                "worstvideo[height>=144][ext=mp4]+worstaudio[ext=m4a]/"  # Worst video + worst audio
                "worstvideo[height>=144][ext=webm]+worstaudio[ext=webm]/"  # Fallback to webm
                "worst[ext=mp4]/"  # Just worst format in mp4 if above not available
                "worst"  # Ultimate fallback to worst of anything
            ),
            "outtmpl": "downloads/%(title)s_video_for_audio_extraction.%(ext)s",
        })
        return base_opts

    # ---------------------------------------------------------
    # CUSTOM FORMAT OPTIONS
    # ---------------------------------------------------------
    @staticmethod
    def get_custom_format_options(format_spec, output_template="downloads/%(id)s_custom.%(ext)s"):
        """
        Get custom format options for specific format requirements.

        Args:
            format_spec (str): Format specification string (e.g., 'bestvideo[height<=1080]+bestaudio')
            output_template (str): Output filename template
        """
        base_opts = YouTubeConfig.get_base_options()
        base_opts.update({
            "format": format_spec,
            "outtmpl": output_template,
        })
        return base_opts

    # ---------------------------------------------------------
    # HIGH QUALITY OPTIONS (4K and above)
    # ---------------------------------------------------------
    @staticmethod
    def get_high_quality_options(max_height=2160):
        """
        Get options for highest quality downloads with specific height limits.

        Args:
            max_height (int): Maximum height in pixels (default 2160 for 4K)
        """
        base_opts = YouTubeConfig.get_base_options()
        base_opts.update({
            "format": (
                f"bestvideo[height<={max_height}][ext=mp4][fps<=60]+bestaudio[ext=m4a]/"
                f"bestvideo[height<={max_height}][ext=webm][fps<=60]+bestaudio[ext=webm]/"
                f"best[height<={max_height}][ext=mp4]/"
                f"best[height<={max_height}][ext=webm]/"
                f"best[height<={max_height}]/"
                f"best"
            ),
            "outtmpl": "downloads/%(id)s_high_quality.%(ext)s",
            "merge_output_format": "mp4",
        })
        return base_opts
