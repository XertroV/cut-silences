import os
from typing import Tuple, List

from moviepy.video.compositing.concatenate import concatenate_videoclips
from moviepy.video.io.VideoFileClip import VideoFileClip
from plumbum import cli, BG, TEE
from plumbum import local

ffmpeg = local.cmd.ffmpeg


class ClipSilences(cli.Application):
    verbose = cli.Flag(["-v", "--verbose"], help="Enable verbose logging")
    in_file = cli.SwitchAttr("-i", help="The input file to read / analyse / convert", mandatory=True)
    duration = cli.SwitchAttr("-d", help="The minimum duration of silences", default=0.5, argtype=float)
    threshold = cli.SwitchAttr("-t", help="silence threshold in dB", default=-30, argtype=cli.Range(-100, 0))

    def info(self, output=None) -> Tuple[int, str, str]:
        print(f'duration: {self.duration}')
        assert self.duration >= 0.5
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
            '-af', f'silencedetect=n={self.threshold}dB:d={self.duration}',  # audio filter, silencedetect
            '-f', 'null',  # output format: null
            '-',  # output to stdout
        ]

    @staticmethod
    def ease_in_and_out(x: float) -> float:
        return 2 * x * x if x < 0.5 else 1 - (-2 * x + 2)**2 / 2

    @staticmethod
    def rescale_silence(start, duration, end) -> Tuple[float, float, float]:
        if duration < 0.5:
            return start, duration, end
        _duration = min([10, ClipSilences.ease_in_and_out(max([0, duration - 0.5]) / 19.5) * 19.5 / 2 + 0.5])
        delta = (duration - _duration) / 2
        return start + delta, _duration, end - delta

    @staticmethod
    def rescale_all_silences(silences: List[Tuple[float, float, float]]) -> List[Tuple[float, float, float]]:
        return list(ClipSilences.rescale_silence(s, d, e) for (s, d, e) in silences)

    @cli.switch("-o", help="The output file")
    def trim_silences(self, silences: List[Tuple[float, float, float]]):
        video = VideoFileClip(self.in_file)
        full_duration = video.duration
        _silences = self.rescale_all_silences(silences)
        non_silent_periods = list(
            [(end1, start2 - end1, start2) for (_, _, end1), (start2, _, _) in zip(_silences[:-1], _silences[1:])])
        print(non_silent_periods)

        input_dir, input_file = os.path.split(self.in_file)
        fname, fext = os.path.splitext(input_file)
        output_fname = os.path.join(input_dir, f"{fname}_NOSILENCE_{self.duration}s.{fext}")
        print(f"writing output to {output_fname}")

        clips = list([video.subclip(s, e) for s, d, e in non_silent_periods if d >= 1])
        output_video = concatenate_videoclips(clips)
        output_video.write_videofile(output_fname, preset='ultrafast', codec='libx264')
        video.close()

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
