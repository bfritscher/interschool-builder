@echo off
setlocal enabledelayedexpansion

set "input_dir=E:\projects\interschool-builder\videos\in"
set "output_dir=E:\projects\interschool-builder\videos\2025"

for %%f in ("%input_dir%\*.*") do (
    set "input_file=%%~ff"
    set "output_file=!output_dir!\%%~nf_cap.mp4"
    ffmpeg -i "!input_file!" -filter:v "setpts=PTS/5,scale=1280:720" -c:v libx264 -crf 23 -preset slow -profile:v main -an "!output_file!"
)

echo All files processed.