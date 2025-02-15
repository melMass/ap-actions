import json
import anchorpoint as ap
from sys import platform
import subprocess
import os
import random
import string

ui = ap.UI()
ctx = ap.Context.instance()
use_prores = False
if ctx.inputs["prores"] == "true":
    use_prores = True
try:
    filename = ctx.filename.split("_")
    filename.pop()
    filename = "_".join(filename) if len(filename) > 1 else ctx.filename
except:
    filename = ctx.filename

is_exr = "exr" in ctx.suffix

def create_random_text():
    ran = "".join(random.choices(string.ascii_uppercase + string.digits, k=10))
    return str(ran)

def concat_demuxer(selected_files, fps):
    # Create a file for ffmpeg within Anchorpoints temp directory.
    # Use a random name so that we do not conflict with any other file
    output = os.path.join(ctx.folder, f"{create_random_text()}.txt")

    # See https://trac.ffmpeg.org/wiki/Concatenate
    file = open(output, "a")
    duration = 1 / int(fps)
    for selected_file in selected_files:
        file.write("file '" + selected_file + f"'\nduration {duration}\n")

    # From the ffmpeg documentation: due to a quirk, the last image has to be specified twice
    file.write("file '" + selected_files[-1] + "'\n")
    file.close()
    return output

def ffmpeg_seq_to_video(ffmpeg_path, selected_files, target_folder, fps):
    # Show Progress
    progress = ap.Progress("FFmpeg", "Converting Sequence to Video", infinite=True)

    # Provide FFmpeg with the set of selected files through the concat demuxer
    concat_file = concat_demuxer(selected_files, fps)
    ext = "mov" if use_prores else "mp4"
    arguments = [
            ffmpeg_path,
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_file,
            "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2",
            "-vsync", "vfr",
            "-pix_fmt", "yuv420p",
            os.path.join(target_folder,f"{filename}.{ext}"),
        ]
    if is_exr:
        arguments.insert(1,"-apply_trc")
        arguments.insert(2,"iec61966_2_1")
    if use_prores:
        filepth = arguments.pop()
        arguments.append("-vcodec")
        arguments.append("prores_ks")
        arguments.append("-profile:v")
        arguments.append("4444")
        arguments.append("-alpha_bits")
        arguments.append("16")
        arguments[arguments.index("-pix_fmt") + 1] = "yuva444p10le"
        arguments.append(filepth)

    ffmpeg = subprocess.run(
        arguments, capture_output=True
    )
    if ffmpeg.returncode != 0:
        print(ffmpeg.stderr)
        ui.show_error("Failed to export video", description="Check Anchorpoint Console")
    else:
        ui.show_success("Export Successful", description="Created video.mp4")

    # Do some cleanup
    os.remove(concat_file)

# First, check if the tool can be found on the machine
ffmpeg_path = None
if platform == "darwin":
    ffmpeg_path = ctx.inputs["ffmpeg_mac"]
elif platform == "win32":
    ffmpeg_path = ctx.inputs["ffmpeg_win"]

if (ap.check_application(ffmpeg_path, f"Could not find ffmpeg! Make sure ffmpeg is set up correctly in {ctx.yaml}")):
    if len(ctx.selected_files) > 0:
        # Convert the image sequence to a video
        # We don't want to block the Anchorpoint UI, hence we run on a background thread
        ctx.run_async(ffmpeg_seq_to_video, ffmpeg_path, ctx.selected_files, ctx.folder, ctx.inputs["fps"])
