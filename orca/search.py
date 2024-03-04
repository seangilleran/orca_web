"""TODO: File description."""

import logging
from pathlib import Path

log = logging.getLogger(__name__)


def load_search_cache(batch_path):
    """TODO: Description."""
    import json

    search_index = []
    search_index_file = Path(batch_path) / 'cache' / 'searches' / 'search_index.json'
    if search_index_file.exists():
        with search_index_file.open() as f:
            search_index = json.load(f)
    else:
        search_index_file.parent.mkdir(parents=True, exist_ok=True)
        search_index_file.write_text('[]\n')
    return search_index, search_index_file


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
    count = 0
    start = time()
    with whoosh_index.searcher() as searcher:
        parser = QueryParser('content', whoosh_index.schema)
        parser.add_plugin(FuzzyTermPlugin())
        query = parser.parse(query_str)
        query_results = searcher.search(query, limit=None)

        # Get the UUID of each result and match it against our file index.
        for result in query_results:
            yield next(r for r in index['images'] if r['uuid'] == result['uuid'])
            count += 1

    log.info(
        'Found %d results for "%s" in %d documents. Search took %.2f seconds.'
        % (count, query_str, len(index['images']), time() - start)
    )


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
    search_info = {
        'uuid': f"{uuid4()}",
        'query_str': query_str,
        'timestamp': search_ts,
        'results': {
            'json_path': f"{search_file}",
            'count': 0,
            'complete': False,
        },
    }

    # Check the cache--have we done this search before?
    search_index, search_index_file = load_search_cache(batch_path)
    for search in search_index:
        if query_str == search['query_str']:
            search_info.update(search)
            search_file = Path(search_info['results']['json_path'])
            is_complete = search_info['results']['complete']
            if search_file.exists() or search_file.is_file() and is_complete:
                with search_file.open() as f:
                    results = json.load(f)
            return results, search_info
    
    # If not, start a new search.
    results = []
    search_index.append(search_info)
    search_file = Path(search_info['results']['json_path'])
    for result in whoosh_query(query_str, batch_path):
        results.append(result)
        search_info['results']['count'] = len(results)
        with search_index_file.open('w') as f:
            json.dump(search_index, f)
        with search_file.open('w') as f:
            json.dump(results, f)

    search_info['results']['complete'] = True
    with search_index_file.open('w') as f:
            json.dump(search_index, f)
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
