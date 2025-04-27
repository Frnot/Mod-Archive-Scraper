import os
import shutil
import subprocess
import multiprocessing
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from pydub import AudioSegment # install audioop-lts

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
                title = row.find('td', width='300').get_text(strip=True)
                mod_files[file_name] = (download_link, title)

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
    if shutil.which("openmpt123") and shutil.which("ffmpeg"):
        os.makedirs(rendered, exist_ok=True)
        # batch render mod files
        with multiprocessing.Pool(processes=6) as pool:
            for name,(_,title) in mod_files.items():
                pool.apply_async(render, args=(name, title))
            pool.close()
            pool.join()

            

def download(mod_files):
    # download mod files
    os.makedirs(mod_dir, exist_ok=True)
    for url, title in mod_files.values():
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


def render(name, title):
    mod_filepath = os.path.join(mod_dir, name)
    wav_filepath = mod_filepath+".wav"
    rendered_filepath = os.path.join(rendered, title+".flac")

    subprocess.run(["openmpt123", "--render", mod_filepath])
    print(f"Converting {wav_filepath} to {rendered_filepath}.")
    audio = AudioSegment.from_wav(wav_filepath)
    audio = audio.set_frame_rate(44100) # 44.1kHz
    audio = audio.set_sample_width(2)    # 16 bits per sample
    audio.export(rendered_filepath, format="flac", parameters=["-compression_level", "12"])
    os.remove(wav_filepath)


if __name__ == "__main__":
    main()