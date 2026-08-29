"""videogen - assemble images, clips, captions and audio into a video."""

from .build import Result, render
from .ffmpeg import FFmpegError, Tools
from .manifest import Spec, SpecError, from_directory, load

__version__ = "0.1.0"
__all__ = ["render", "Result", "Spec", "SpecError", "FFmpegError", "Tools",
           "load", "from_directory"]
