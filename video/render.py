"""Render film.html to frames with Playwright, then to MP4 with ffmpeg.

    python video/render.py            # full render -> video/mise-launch.mp4
    python video/render.py --sheet    # 12-frame contact sheet for the critique loop
"""
import asyncio, subprocess, sys, shutil
from pathlib import Path
from playwright.async_api import async_playwright

HERE = Path(__file__).parent
FRAMES = HERE / "frames"
SHEET_T = [0.9, 2.1, 3.9, 4.75, 6.2, 7.5, 8.6, 11.8, 14.2, 16.6, 17.7, 19.6]


async def shoot(times, out_names):
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={"width": 1920, "height": 1080})
        await pg.goto((HERE / "film.html").resolve().as_uri())
        await pg.wait_for_function("window.READY === true")
        await pg.wait_for_timeout(300)
        for t, name in zip(times, out_names):
            await pg.evaluate(f"render({t})")
            await pg.screenshot(path=str(name), type="png" if name.suffix == ".png" else "jpeg", **({} if name.suffix == ".png" else {"quality": 95}))
        await b.close()


def main():
    if "--sheet" in sys.argv:
        out = [HERE / f"_sheet_{i:02d}.png" for i in range(len(SHEET_T))]
        asyncio.run(shoot(SHEET_T, out))
        from PIL import Image
        tiles = [Image.open(o).resize((640, 360)) for o in out]
        sheet = Image.new("RGB", (640 * 3, 360 * 4), "white")
        for i, im in enumerate(tiles):
            sheet.paste(im, ((i % 3) * 640, (i // 3) * 360))
        sheet.save(HERE / "contact_sheet.png")
        for o in out:
            o.unlink()
        print("contact sheet ->", HERE / "contact_sheet.png")
        return
    shutil.rmtree(FRAMES, ignore_errors=True); FRAMES.mkdir()
    fps, dur = 30, 20
    times = [i / fps for i in range(fps * dur)]
    asyncio.run(shoot(times, [FRAMES / f"f{i:04d}.jpg" for i in range(len(times))]))
    audio = HERE / "score.wav"
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps), "-i", str(FRAMES / "f%04d.jpg")]
    if audio.exists():
        cmd += ["-i", str(audio), "-c:a", "aac", "-b:a", "192k", "-shortest"]
    cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "22", "-preset", "slow", "-movflags", "+faststart", str(HERE / "mise-launch.mp4")]
    subprocess.run(cmd, check=True)
    shutil.rmtree(FRAMES)
    print("video ->", HERE / "mise-launch.mp4")


if __name__ == "__main__":
    main()
