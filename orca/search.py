"""TODO: File description."""

import logging
from pathlib import Path

log = logging.getLogger(__name__)


def load_cached_search(query_str, batch_path):
    """TODO: Description."""
    import json

    log.info('Looking for cached searches...')
    batch_path = Path(batch_path)
    search_path = batch_path / 'cache' / 'searches'

    search_index_file = search_path / 'search_index.json'
    if not search_index_file.exists():
        search_index_file.parent.mkdir(parents=True, exist_ok=True)
        with search_index_file.open('w') as f:
            f.write('[]\n')
    with search_index_file.open() as f:
        search_cache = json.load(f)

    search_info = search_file = None
    for search in search_cache:
        if query_str == search['query_str']:
            search_info = search
            search_file = Path(search['path'])
            break

    if not search_info:
        log.debug('No cached search found for "%s".' % query_str)
        return None
    if not search_file.exists():
        log.warning('File not found: %s' % search_file)
        return None

    log.info('Found cached search for "%s": %s' % (query_str, search_file))
    with search_file.open() as f:
        results = json.load(f)

    return results, search_info


def search(query_str, batch_path):
    """TODO: Description."""
    import json
    from datetime import datetime
    from uuid import uuid4
    from slugify import slugify
    from whoosh.index import open_dir
    from whoosh.qparser import QueryParser, FuzzyTermPlugin

    # Load cache.
    batch_path = Path(batch_path)
    cache_path = batch_path / 'cache'
    cached = load_cached_search(query_str, batch_path)
    if cached is not None:
        log.info('Found %d results for "%s" (cached).' % (len(cached[0]), query_str))
        return cached

    search_index_file = cache_path / 'searches' / 'search_index.json'
    with search_index_file.open() as f:
        search_cache = json.load(f)

    # Load indeces.
    index_file = cache_path / 'index.json'
    with index_file.open() as f:
        index = json.load(f)
    log.info(
        'Querying "%s" against %d documents...' % (query_str, len(index['images']))
    )

    whoosh_index_path = cache_path / 'whoosh'
    whoosh_index = open_dir(whoosh_index_path.as_posix())

    # Parse Whoosh query and store results.
    search_ts = datetime.now().isoformat()
    results = []
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
        'Found %d results for "%s" in %d documents.'
        % (len(results), query_str, len(index['images']))
    )

    # Save cached results.
    search_name = f"{slugify('-'.join(search_ts.split('-')[:-1])).replace('t', '_')}_{slugify(query_str)}"
    search_file = cache_path / 'searches' / f"{search_name}.json"
    log.info('Saving cached search: %s' % search_file)
    with search_file.open('w') as f:
        json.dump(results, f)

    # Create markdown file containing search results ("megadoc").
    md_path = batch_path / 'cache' / 'megadocs'
    md_path.mkdir(parents=True, exist_ok=True)
    md_file = md_path / f"{slugify(f'{search_name} {query_str}')}.txt"
    docx_file = md_file.with_suffix('.docx')

    # Save these results to our index of cached searches.
    search_info = {
        'uuid': f"{uuid4()}",
        'query_str': query_str,
        'timestamp': search_ts,
        'path': f"{search_file}",
        'md_path': f"{md_file}",
        'docx_path': f"{docx_file}",
    }
    search_cache.append(search_info)
    with search_index_file.open('w') as f:
        json.dump(search_cache, f)

    # Return tuple containing both results and metadata.
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
