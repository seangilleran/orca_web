"""
TODO: File description.
"""

import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)


def login(username='', password=''):
    """
    Login to iCloud and return session handle to API.
    Adapted from https://github.com/picklepete/pyicloud.
    """
    from pyicloud import PyiCloudService

    if not username:
        username = os.getenv('ORCA_ICLOUD_USER')
    if not password:
        password = os.getenv('ORCA_ICLOUD_PASS')
    log.info('Logging into iCloud as %s...' % username)
    api = PyiCloudService(username, password)

    if api.requires_2fa:
        print('Two-factor authentication required.')
        code = input('Enter the code you received: ')

        result = api.validate_2fa_code(code)
        print(f"Code validation result: {result}")
        if not result:
            print('Failed to verfiy security code.')
            exit(1)

        if not api.is_trusted_session:
            print('Session is not trusted. Requesting trust...')
            result = api.trust_session()
            print(f"Session trust result: {result}")
            if not result:
                print("Failed to request trust.")
                exit(1)

    elif api.requires_2sa:
        import click

        print('Two-step authentication required. Your trusted devices are:')
        devices = api.trusted_devices
        for i, device in enumerate(devices):
            print(f"{i}: {device.get('deviceName', device.get('phoneNumber'))}")
            device = click.prompt('Which device would you like to use?', default=0)

            device = devices[device]
            if not api.send_verification_code(device):
                print('Failed to send verification code.')
                exit(1)

    return api


def download_album(
    dl_path, album_name, api, retry_max=3, retry_delay=60.0, skip_video=True
):
    """
    Download photos from an album and save them to the specified path.

    The downloaded photos will be named with a timestamp and the original
    filename to help sort them by the order they were taken. The filesystem
    timestamps are also adjusted to reflect the "created on" property from
    iCloud, providing an additional way to sort the photos.
    """
    import time
    from pyicloud.exceptions import PyiCloudAPIResponseException

    dl_path = Path(dl_path)
    album = api.photos.albums.get(album_name)
    if not album:
        log.error('Album not found: %s' % album_name)
        return None

    count = len(album)
    dl_count = 0
    log.info('Downloading %d photos from album "%s"...' % (count, album_name))
    dl_path.mkdir(exist_ok=True, parents=True)
    for i, photo in enumerate(album):

        # Build filename.
        index = f"{(i + 1):06}"
        timestamp = photo.created.strftime('%Y-%m-%d_%H-%M-%S')
        name = photo.filename
        img_file = dl_path / f"{index}_{timestamp}_{name}"
        count_str = '[%d/%d]: %s' % (i + 1, count, img_file)
        if i == 0 or i % 100 == 99 or i == count - 1:
            log.info(count_str)
        else:
            log.debug(count_str)

        if img_file.exists():
            log.warning('Already exists, skipping: %s' % img_file)
            continue
        if skip_video and img_file.suffix.lower() == '.mov':
            log.warning('Video, skipping: %s' % img_file)
            continue

        # Download photo.
        attempt = 0
        while attempt == 0 or attempt < retry_max:
            try:
                download = photo.download()
                break
            except PyiCloudAPIResponseException:
                log.error('Failed with code 503.')
                if attempt < retry_max:
                    log.info(
                        'Retrying in %f seconds (%d/%d)...'
                        % (retry_delay, attempt + 1, retry_max)
                    )
                    attempt += 1
                    time.sleep(retry_delay)

        # Buffer so we don't have to keep the whole thing in RAM.
        with img_file.open('wb') as f:
            for chunk in download.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)
        dl_count += 1

        # Overwrite filesystem timestamp with iCloud's "created on" property,
        # just as another way to help sort them if necessary.
        timestamp = time.mktime(photo.created.timetuple())
        os.utime(img_file, (timestamp, timestamp))

    log.info('Done! Got %d of %d photos from "%s."' % (dl_count, count, album_name))


if __name__ == '__main__':
    import argparse
    from dotenv import load_dotenv

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
    )

    load_dotenv()
    api = login()
    album_folder = Path('data/img/2023-06')
    album_name = 'June 2023'
    download_album(album_folder, album_name, api)
