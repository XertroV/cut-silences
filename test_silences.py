import sys
import traceback

from main import ClipSilences


def test():
    zipped_silences_and_expected = [
        ((20, 0, 20), (20, 0, 20)),
        ((20, 0.5, 20.5), (20, 0.5, 20.5)),
        ((5, 0.5, 5.5), (5, 0.5, 5.5)),
        ((0, 20, 20), (5, 10, 15)),
        ((0, 9.75, 9.75), (4.875/2, 4.875, 4.875/2*3))
    ]
    fails = 0
    unk = 0
    for (silence, expected) in zipped_silences_and_expected:
        output = ClipSilences.rescale_all_silences([silence])[0]
        try:
            _o = list(output)
            _e = list(expected)
            for (o, e) in zip(_o, _e):
                assert abs(o - e) < 0.1
        except AssertionError as e:
            fails += 1
            print(f"Input: {silence}, Data: {output}, Expected: {expected}")
            # traceback.print_tb(e.__traceback__)
        except Exception as e:
            unk += 1
            traceback.print_tb(e.__traceback__)
        else:
            print(f"Passed: {silence} -> {expected}")

    sys.exit(fails == 0 and unk == 0)


if __name__ == "__main__":
    test()
