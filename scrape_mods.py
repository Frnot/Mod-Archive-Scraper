import os
import shutil
import subprocess
import multiprocessing
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from pydub import AudioSegment # install audioop-lts
from mutagen.flac import FLAC

mod_dir = "mods"
rendered = "rendered"

mainurl = "https://modarchive.org/index.php?request=view_artist_modules&query=84384"


def main():
    # collect list of mod files
    url = mainurl
    mod_files = {}
    while True:
        response = requests.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')

        # Get all download links on this page
        for row in soup.find_all('tr'):
            if download_a := row.find('a', title='Download'):
                download_link = download_a['href']
                file_name = download_link.split('#')[-1]
                mod_files[file_name] = download_link

        # Find the "next page" link
        next_button = soup.find('a', class_='pagination', string='>')
        if next_button:
            next_href = next_button['href']
            url = urljoin(url, next_href)
        else:
            break

    # download the mod files
    download(mod_files)

    # render if openmpt123 and ffmpeg are installed
    if not shutil.which("openmpt123"):
        print("Cant find openmpt123")
        return
    if not shutil.which("ffmpeg"):
        print("Cant find ffmpeg")
        return

    os.makedirs(rendered, exist_ok=True)
    # batch render mod files
    with multiprocessing.Pool(processes=6) as pool:
        for name in mod_files.keys():
            pool.apply_async(render, args=(name,))
            render(name)
        pool.close()
        pool.join()

            

def download(mod_files):
    # download mod files
    os.makedirs(mod_dir, exist_ok=True)
    for url in mod_files.values():
        # Get the filename from url
        filename = url.split('#')[-1]
        save_path = os.path.join(mod_dir, filename)

        if (os.path.exists(save_path)):
            print(f"{filename} already exists. skipping.")
            continue

        print(f'Downloading {filename}...')
        response = requests.get(url)
        
        if response.status_code == 200:
            with open(save_path, 'wb') as f:
                f.write(response.content)
        else:
            print(f'Failed to download {url}')


def render(name):
    mod_filepath = os.path.join(mod_dir, name)
    wav_filepath = mod_filepath+".wav"
    flacname = os.path.splitext(name)[0]+".flac"
    flac_filepath = os.path.join(rendered, flacname)
    print(f"Converting {wav_filepath} to {flac_filepath}.")
    # render mod file
    subprocess.run(["openmpt123", "--render", mod_filepath])
    # convert to flac
    audio = AudioSegment.from_wav(wav_filepath)
    audio = audio.set_frame_rate(44100) # 44.1kHz
    audio = audio.set_sample_width(2)   # 16 bits per sample
    audio.export(flac_filepath, format="flac", parameters=["-compression_level", "12"])
    # copy title from metadata
    title = extract_title(mod_filepath)
    flac = FLAC(flac_filepath)
    flac["title"] = title
    flac.save()
    # remove wav file
    #os.remove(wav_filepath)


def extract_title(mod_filepath):
    with open(mod_filepath, 'rb') as f:
        header = f.read(1084)  # read enough to detect formats

    # Check for XM
    if header.startswith(b'Extended Module: '):
        title = header[17:37].decode('ascii', errors='ignore').strip()

    # Check for S3M
    elif header[44:48] == b'SCRM':
        title = header[0:28].decode('ascii', errors='ignore').strip()

    # Check for IT (Impulse Tracker)
    elif header[0:4] == b'IMPM':
        title = header[4:26].decode('ascii', errors='ignore').strip()

    # Check for MOD
    else:
        magic = header[1080:1084]
        known_mod_magic = [
            b'M.K.', b'M!K!', b'4CHN', b'6CHN', b'8CHN',
            b'FLT4', b'FLT8', b'OKTA', b'CD81'
        ]
        if magic in known_mod_magic:
            title = header[0:20].decode('ascii', errors='ignore').strip()
        else:
            title = 'Unknown'

    return title


if __name__ == "__main__":
    main()