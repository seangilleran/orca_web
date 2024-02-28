"""TODO: File description."""

import logging
from pathlib import Path

log = logging.getLogger(__name__)


def load_img_data(img, batch):
    """TODO: Description."""
    from uuid import uuid4
    from dateutil.parser import parse

    img = Path(img)
    batch = Path(batch)

    img_split = img.stem.split('_')
    img_index = (int)(img_split[0])
    img_ts = parse(f"{img_split[1]} {img_split[2].replace('-', ':')}")
    img_ts_str = img_ts.strftime('%B %d, %Y at %-I:%M %p')
    img_title = "_".join(img_split[3:])

    img_uuid = uuid4()

    album_path = img.parent
    album = f"{album_path.name}"
    album_title = parse(album).strftime('%B %Y')

    json = batch / album / 'json' / f"{img.stem}.json"
    if not json.exists():
        log.warning('File not found: %s' % json)
        json = ''

    txt = batch / album / 'txt' / f"{img.stem}.txt"
    if not txt.exists():
        log.warning('File not found: %s' % txt)
        txt = ''

    img_data = {
        'uuid': f"{img_uuid}",
        'index': img_index,
        'title': img_title,
        'timestamp': img_ts.isoformat(),
        'timestamp_str': img_ts_str,
        'path': f"{img}",
        'json_path': f"{json}",
        'txt_path': f"{txt}",
        'album': album,
        'album_title': album_title,
        'album_path': f"{album_path}",
    }
    return img_data


def make_index(batch):
    """TODO: Description."""
    from uuid import uuid4
    from datetime import datetime
    from natsort import natsorted

    batch = Path(batch)
    cache_path = batch / 'cache'
    data_path = batch.parent
    img_path = data_path / 'img'

    log.info('Loading images for %s...' % batch)
    img_files = natsorted([f for f in img_path.glob('**/*.*') if f.is_file()])
    log.info('Found %d images. Indexing metadata...' % len(img_files))

    index = {
        'schema': "orca_v1",
        'uuid': f"{uuid4()}",
        'batch': f"{batch.name}",
        'cache_path': f"{cache_path}",
        'timestamp': datetime.now().isoformat(),
        'images': [],
    }
    for i, img in enumerate(img_files):
        log.debug('[%d/%d] %s' % (i + 1, len(img_files), img))
        img_data = load_img_data(img, batch)
        index['images'].append(img_data)

    return index


def make_whoosh_index(index):
    """TODO: Description."""
    from whoosh.fields import Schema, TEXT, ID
    from whoosh.index import create_in
    from whoosh.writing import AsyncWriter

    whoosh_index_path = Path(index['cache_path']) / 'whoosh'
    whoosh_index_path.mkdir(parents=True, exist_ok=True)
    log.info('Creating Whoosh index in %s...' % whoosh_index_path)

    schema = Schema(
        uuid=ID(stored=True, unique=True),
        content=TEXT(stored=True),
    )

    whoosh_index = create_in(whoosh_index_path.as_posix(), schema)
    writer = AsyncWriter(whoosh_index)

    for i, img in enumerate(index['images']):
        log.debug('[%d/%d] %s' % (i + 1, len(index['images']), img['path']))

        # Check for associated metadata and OCR files.
        json_file = Path(img.get('json_path', ''))
        if not json_file.is_file():
            log.warning('Skipping, JSON file not found: %s' % img['path'])
            continue
        txt_file = Path(img.get('txt_path', ''))
        if not txt_file.is_file():
            log.warning('Skipping, TXT file not found: %s' % img['path'])
            continue

        # Load content.
        with txt_file.open() as f:
            content = f.read()
        writer.add_document(uuid=img['uuid'], content=content)

    log.info('Saving Whoosh index to %s...' % whoosh_index_path)
    writer.commit()


if __name__ == '__main__':
    import argparse
    import json

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
    )

    parser = argparse.ArgumentParser()
    parser.add_argument('batch_path')
    args = parser.parse_args()

    # Make index from batch.
    batch_path = Path(args.batch_path)
    index = make_index(batch_path)

    # Save index to file.
    cache_path = Path(index['cache_path'])
    cache_path.mkdir(parents=True, exist_ok=True)
    index_file = cache_path / 'index.json'
    with index_file.open('w') as f:
        json.dump(index, f)

    # Make Whoosh index.
    make_whoosh_index(index)
