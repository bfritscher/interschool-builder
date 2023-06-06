@echo off
setlocal enabledelayedexpansion

set "input_dir=C:\temp\demo_videos"
set "output_dir=C:\temp\out"

for %%f in ("%input_dir%\*.*") do (
    set "input_file=%%~ff"
    set "output_file=!output_dir!\%%~nf_cap.mp4"
    ffmpeg -i "!input_file!" -filter:v "setpts=PTS/5" -an "!output_file!"
)

echo All files processed.