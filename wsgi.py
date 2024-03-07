"""TODO: File description."""

import json
import os
from pathlib import Path
from uuid import uuid4

from celery import Celery
from flask import (
    Flask,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)


app = Flask(__name__)
app.secret_key = os.getenv('ORCA_FLASK_SECRET', f"{uuid4()}")
celery = Celery(
    __name__,
    broker=os.getenv('ORCA_BROKER_URL', 'redis://localhost:6379/0'),
    backend=os.getenv('ORCA_BACKEND_URL', 'redis://localhost:6379/0'),
)
celery.conf.update(app.config)
batch_path = Path(os.getenv('ORCA_CURRENT_BATCH_PATH', 'data/00_initial'))

with (batch_path / 'cache' / 'index.json').open() as f:
    doc_count = len(json.load(f)['images'])


@celery.task(bind=True)
def do_search(self, query_str):
    """TODO: Description."""
    from orca.search import search
    from orca.megadoc import build_from_search

    print(f"Searching: {query_str}")
    search(query_str, batch_path)
    build_from_search(query_str, batch_path)
    print(f"Search complete: {query_str}")


@app.route('/orca/api/index')
def api_get_index():
    """TODO: Description."""
    import time
    from orca.search import load_search_cache

    retries = 3
    while retries > 0:
        search_index, _ = load_search_cache(batch_path)
        if search_index:
            break
        time.sleep(0.1)
        retries -= 1
    return jsonify(search_index)


@app.route('/orca/search', methods=['GET', 'POST'])
def search():
    """TODO: Description."""
    import time

    if request.method == 'POST':
        query_str = request.form['query']
        do_search.delay(query_str)
        time.sleep(2)
        return redirect(url_for('search'))

    return render_template('search.html', total=doc_count)
