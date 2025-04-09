import base64
import itertools
import math
import os
import random
import sys
import zlib
from functools import partial
from io import StringIO
from pathlib import Path

import PIL.Image

CHARSET = dict.fromkeys(chr(i) for i in range(32, 127))
del CHARSET["\\"]
# del CHARSET['"']
CHARSET = list(CHARSET)


def get_combinations_count(total_n, combo_n):
    return math.factorial(total_n) / (
        math.factorial(combo_n) * math.factorial(total_n - combo_n)
    )


def get_combinations(iterable, n):
    return ("".join(x) for x in itertools.combinations_with_replacement(iterable, n))


def open_image(path: Path):
    try:
        return path.is_file() and PIL.Image.open(path)
    except:
        pass  # print(f"Error opening image {path}")


def encode_xpm(img: PIL.Image.Image, charset=None, quantize=256):
    if quantize:
        img = img.quantize(quantize)
    charset = charset or CHARSET

    colors = [
        False if a == 0 else (r, g, b) for r, g, b, a in img.convert("RGBA").getdata()
    ]
    palette = sorted(set(colors), key=lambda x: x if x else (-1,))
    pixelWidth, pixelCapacity = next(
        (n, w)
        for n in range(1, 12)
        if (w := get_combinations_count(len(charset), n)) >= len(palette)
    )
    color2symbol = {}

    # TODO: if our pixelCapacity is much higher than our palette size we may want to quantize down to the previous pixelWidth, but PIL only supports quantizing to 256 colors
    # print(f"\tPallete Efficiency: {len(palette)/pixelCapacity*100: 6.2f} %")

    with StringIO() as f:
        f.write(f"{img.width} {img.height} {len(palette)} {pixelWidth}\n")
        symbolGenerator = get_combinations(charset, pixelWidth)

        for color in palette:
            symbol = next(symbolGenerator)
            hexColor = "#" + "".join(f"{n:02X}" for n in color) if color else "None"
            f.write(f"{symbol} c {hexColor}\n")
            color2symbol[color] = symbol

        for y in range(img.height):
            for x in range(img.width):
                color = colors[y * img.width + x]
                symbol = color2symbol[color]
                f.write(symbol)
            f.write("\n")

        return f.getvalue()[:-1]


def main():
    os.chdir(Path(__file__).parent)
    os.makedirs("output", exist_ok=True)

    candidates: dict[Path, str] = {}

    for path in Path(".").iterdir():
        if img := open_image(path):
            with img as img:

                def do_image(img: PIL.Image.Image, encoder, path: Path):
                    print(path.stem)

                    if False:
                        charset = CHARSET
                        xpm = ""
                        xpm_size = sys.maxsize
                        xpm_size_worst = -sys.maxsize
                        for _ in range(1000):
                            new = encoder(img, charset=charset)
                            new_size = len(
                                base64.b85encode(zlib.compress(new.encode()))
                            )
                            if new_size > xpm_size_worst:
                                xpm_size_worst = new_size
                                print(f"\t\t>{xpm_size_worst}")
                            if new_size < xpm_size:
                                xpm = new
                                xpm_size = new_size
                                print(f"\t{xpm_size}<")
                            charset = CHARSET[:]
                            random.shuffle(charset)
                    else:
                        xpm = encoder(img)
                    candidates[path.stem] = xpm
                    with ("output" / path).open("w") as f:
                        f.write(xpm)

                do_image(img, encode_xpm, path.with_suffix(".xpm.txt"))
                do_image(
                    img,
                    partial(encode_xpm, quantize=None),
                    path.with_suffix(".xpm.FULL.txt"),
                )

    result = {}
    for name, xpm in candidates.items():
        result[f"{name}.decode.txt"] = {
            "value": (
                (d := base64.b85encode(zlib.compress(xpm.encode())).decode("ascii"))
            ),
            "size": len(str(d)),
            "code": (code := f"zlib.decompress(base64.b85decode({repr(d)})).decode()"),
            "codesize": len(code),
        }
        # result[f"{name}.Zlib_base85_bytes.txt"] = {
        #     "value": (d := base64.b85encode(zlib.compress(xpm.encode()))),
        #     "size": len(str(d)),
        #     "code": (code := f"zlib.decompress(base64.b85decode({repr(d)})).decode()"),
        #     "codesize": len(code),
        # }
        # result[f"{name}.Zlib_bytes.txt"] = {
        #     "value": (d := zlib.compress(xpm.encode())),
        #     "size": len(str(d)),
        #     "code": (code := f"{repr(d)}.decode()"),
        #     "codesize": len(code),
        # }
        # result[f"{name}.base85_Zlib_bytes.txt"] = {
        #     "value": (d := zlib.compress(base64.b85encode(xpm.encode()))),
        #     "size": len(str(d)),
        #     "code": (code := f"base64.b85decode(zlib.decompress({repr(d)})).decode()"),
        #     "codesize": len(code),
        # }

    smallest = sorted(result.items(), key=lambda x: x[1]["codesize"])
    pad = len(max(result, key=len))
    for name, data in smallest:
        print(f"{name:{pad+2}} {data['size']:6} ({data['codesize']:6})")
        with Path("output", name).open("w") as f:
            f.write(str(data["code"]))


if __name__ == "__main__":
    main()
