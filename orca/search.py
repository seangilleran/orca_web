"""TODO: File description."""

import logging
from pathlib import Path

log = logging.getLogger(__name__)


def whoosh_query(query_str, batch_path):
    """TODO: Description."""
    import json
    from time import time
    from whoosh.index import open_dir
    from whoosh.qparser import QueryParser, FuzzyTermPlugin

    # Load indeces.
    cache_path = Path(batch_path) / 'cache'
    index_file = cache_path / 'index.json'
    with index_file.open() as f:
        index = json.load(f)
    whoosh_index_path = cache_path / 'whoosh'
    whoosh_index = open_dir(whoosh_index_path.as_posix())

    # Parse query and store results.
    results = []
    start = time()
    with whoosh_index.searcher() as searcher:
        parser = QueryParser('content', whoosh_index.schema)
        parser.add_plugin(FuzzyTermPlugin())
        query = parser.parse(query_str)
        query_results = searcher.search(query, limit=None)

        # Get the UUID of each result and match it against our file index.
        for result in query_results:
            img = next(r for r in index['images'] if r['uuid'] == result['uuid'])
            results.append(img)

    log.info(
        'Found %d results for "%s" in %d documents. Search took %.2f seconds.'
        % (len(results), query_str, len(index['images']), time() - start)
    )
    return results


def search(query_str, batch_path):
    """TODO: Description."""
    import json
    from datetime import datetime
    from uuid import uuid4
    from slugify import slugify

    log.info('Searching for "%s"...' % query_str)
    batch_path = Path(batch_path)

    # Create new search metadata; overwrite later if the search is cached.
    search_ts = datetime.now().isoformat()
    search_name = f"{'-'.join(slugify(search_ts).split('-')[:-1]).replace('t', '_')}_{slugify(query_str)}"
    search_file = batch_path / 'cache' / 'searches' / f"{search_name}.json"
    txt_file = batch_path / 'cache' / 'megadocs' / f"{search_name}.txt"
    docx_file = batch_path / 'cache' / 'megadocs' / f"{search_name}.docx"
    search_info = {
        'uuid': f"{uuid4()}",
        'query_str': query_str,
        'timestamp': search_ts,
        'path': f"{search_file}",
        'txt_path': f"{txt_file}",
        'docx_path': f"{docx_file}",
    }

    # Check the cache--have we done this search before?
    search_index = []
    search_index_file = batch_path / 'cache' / 'searches' / 'search_index.json'
    if search_index_file.exists():
        with search_index_file.open() as f:
            search_index = json.load(f)
    else:
        search_index_file.parent.mkdir(parents=True, exist_ok=True)
        search_index_file.write_text('[]\n')

    is_new_search = True
    for search in search_index:
        if query_str == search['query_str']:
            log.info('Found cached search: %s' % search['path'])
            search_info.update(search)
            is_new_search = False
            break

    # Save the cache here now that we have our entry lined up.
    if is_new_search:
        search_index.append(search_info)
        with search_index_file.open('w') as f:
            json.dump(search_index, f)

    # Perform the search if we haven't already.
    results = []
    search_file = Path(search_info['path'])
    if not search_file.exists() or not search_file.is_file():
        results = whoosh_query(query_str, batch_path)
        with search_file.open('w') as f:
            json.dump(results, f)
    else:
        with search_file.open() as f:
            results = json.load(f)
    return results, search_info


if __name__ == '__main__':
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
    )

    parser = argparse.ArgumentParser()
    parser.add_argument('query')
    parser.add_argument('-b', '--batch_path', required=True)
    args = parser.parse_args()

    results = search(args.query, args.batch_path)
    log.info('Done!')
