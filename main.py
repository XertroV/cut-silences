import os
from typing import Tuple, List

import moviepy.video.compositing as compositing
from moviepy.audio.io.AudioFileClip import AudioFileClip
from moviepy.video.compositing.concatenate import concatenate_videoclips
from moviepy.video.io.VideoFileClip import VideoFileClip
import moviepy.editor as mpy
from plumbum import cli, BG, TEE
from plumbum import local
from plumbum.cli import switches

ffmpeg = local.cmd.ffmpeg


class ClipSilences(cli.Application):
    verbose = cli.Flag(["-v", "--verbose"], help="Enable verbose logging")
    in_file = cli.SwitchAttr("-i", help="The input file to read / analyse / convert", mandatory=True)
    min_duration = cli.SwitchAttr("--s-min", help="The minimum duration of silences", default=0.5, argtype=float)
    max_duration = cli.SwitchAttr("--s-max", help="The maximum duration of silences", default=6, argtype=float)
    threshold = cli.SwitchAttr("-t", help="silence threshold in dB", default=-30, argtype=cli.Range(-100, 0))
    codec = cli.SwitchAttr("--codec-video", help="video encoding library",
                           argtype=cli.Set("h264_vaapi", "h264_nvenc", "libx264", "h264_v4l2m2m", str))
    audio_codec = cli.SwitchAttr("--codec-audio", help="video encoding library", default="libvorbis",
                                 argtype=cli.Set("libvorbis", "libmp3lame", "libfdk_aac", str))

    def info(self, output=None) -> Tuple[int, str, str]:
        print(f'duration: {self.min_duration}')
        assert self.min_duration >= 0.5
        assert len(self.in_file) > 0
        ffmpeg_cmd = self.mk_ffmpeg_bound_command()
        print(f'Running ffmpeg command: {ffmpeg_cmd}')
        _cmd = (ffmpeg_cmd > output) if output else ffmpeg_cmd
        return _cmd & TEE

    def mk_ffmpeg_bound_command(self):
        return ffmpeg[
            '-hide_banner',
            '-vn',  # disable video 'recording'
            '-i', self.in_file,
            '-af', f'silencedetect=n={self.threshold}dB:d={self.min_duration}',  # audio filter, silencedetect
            '-f', 'null',  # output format: null
            '-',  # output to stdout
        ]

    @staticmethod
    def ease_in_and_out(x: float) -> float:
        return 2 * x * x if x < 0.5 else 1 - (-2 * x + 2) ** 2 / 2

    @staticmethod
    def rescale_silence(start, duration, end, min_duration=0.5, max_duration=10) -> Tuple[float, float, float]:
        offset = min_duration
        scaling = (max_duration - min_duration) / 2
        if duration < 0.5:
            return start, duration, end
        _duration = min(
            [10, ClipSilences.ease_in_and_out(max([0, duration - offset]) / scaling) * scaling / 2 + offset])
        delta = (duration - _duration) / 2
        return start + delta, _duration, end - delta

    @staticmethod
    def rescale_all_silences(silences: List[Tuple[float, float, float]],
                             min_duration, max_duration) -> List[Tuple[float, float, float]]:
        return list(
            ClipSilences.rescale_silence(s, d, e, min_duration=min_duration, max_duration=max_duration) for (s, d, e) in
            silences)

    @cli.switch("-o", help="The output file")
    def trim_silences(self, silences: List[Tuple[float, float, float]]):
        video = VideoFileClip(self.in_file)
        full_duration = video.duration
        # print(f"pre_silences: {silences}")
        _silences = self.rescale_all_silences(silences, min_duration=self.min_duration, max_duration=self.max_duration)
        # print(f"post_silences: {_silences}")
        non_silent_periods = list(
            [(end1, start2 - end1, start2) for (_, _, end1), (start2, _, _) in zip(_silences[:-1], _silences[1:])])
        print(non_silent_periods)
        input_dir, input_file = os.path.split(self.in_file)
        fname, fext = os.path.splitext(input_file)
        output_fname = os.path.join(input_dir, f"{fname}_NOSILENCE_{self.min_duration}s{fext}")
        tmp_audio_fname = f"{fname}.TEMP_MPY_wvf_snd_custom.ogg"
        tmp_video_fname = f"{fname}.TEMP_MPY_vid_custom{fext}"
        print(f"writing output to {output_fname}")
        clips = list([video.subclip(s, e) for s, d, e in non_silent_periods if d >= 1])
        print(f"got list of clips")
        # comp = mpy.CompositeVideoClip(clips)
        comp = concatenate_videoclips(clips)
        print(f"make composite video clip (no sound yet)")
        comp.write_videofile(tmp_video_fname, codec=self.codec, preset='ultrafast',
                             threads=os.cpu_count() + 1, audio_codec=self.audio_codec)
        print(f"done writing out ${tmp_video_fname}")

        video.close()
        print(f"closed video")
        # print(f"preparing to write audio")
        # comp.audio.write_audiofile(tmp_audio_fname, buffersize=2000000, codec=self.audio_codec)
        # print(f"wrote audio")
        # comp.audio = None
        # print(f"wrote out video, now combining")
        # output_video = VideoFileClip(tmp_video_fname, audio=False)
        # output_video.set_audio(AudioFileClip(tmp_audio_fname))
        # output_video.write_videofile(output_fname)
        # output_video.write_videofile(output_fname, preset='ultrafast', codec=self.codec, threads=os.cpu_count() + 1,
        #                              fps=video.fps)
        print(f"wrote video out")

    def main(self, cmd=cli.Set("info", "trim")):
        (_code, _stdout, _stderr) = self.info()
        silences = []
        for l in _stderr.split('\n'):
            if 'silence_end' not in l:
                continue
            # sample line: [silencedetect @ 0x7fffe351b460] silence_end: 51.2464 | silence_duration: 2.06966
            l2 = l.strip().split('silence_end: ')[1]
            silence_end, rem = l2.split(' ', maxsplit=1)
            silence_duration = rem.split('silence_duration: ')[1]
            end = float(silence_end)
            duration = float(silence_duration)
            start = end - duration
            silences.append((start, duration, end))
        self.trim_silences(silences)


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    print('running')
    ClipSilences.run()
