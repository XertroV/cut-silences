usage: `python3 ./main.py -i ~/Videos/some-video.mkv`

install dependencies: `pip3 install --user -r requirements.txt` (or use a virtual env)

external dependencies:

* ffmpeg
* ffmpeg codecs like libx264 on linux -- not sure what you need for windows / macos

## todo

* parameterise codec and test for gpu/hw encoding and codecs
* figure out how to make the audio stage take a reasonable amount of time (it's too slow)
* make sure using a minimum silence duration of something other than 0.5s works (might have had an issue with 2s but not certain; other things like a change of FPS could have caused anomaly too)
* test it with more than just the .mkv files I generate with OBS
