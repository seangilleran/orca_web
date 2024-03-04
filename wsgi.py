"""TODO: File description."""

import os
from pathlib import Path
from uuid import uuid4

from celery import Celery
from dotenv import load_dotenv
from flask import (
    Flask,
    redirect,
    render_template,
    request,
    url_for,
)


load_dotenv()
app = Flask(__name__)
app.secret_key = f"{uuid4()}"
celery = Celery(
    __name__,
    broker=os.getenv('ORCA_BROKER_URL', 'redis://localhost:6379/0'),
    backend=os.getenv('ORCA_BACKEND_URL', 'redis://localhost:6379/0'),
)
celery.conf.update(app.config)
batch_path = Path(os.getenv('ORCA_CURRENT_BATCH_PATH', 'data/00_initial'))


@celery.task(bind=True)
def do_search(self, query_str):
    """TODO: Description."""
    from orca.search import search
    from orca.megadoc import build_from_search

    print(f"Searching: {query_str}")
    search(query_str, batch_path)
    build_from_search(query_str, batch_path)
    print(f"Search complete: {query_str}")


@app.template_filter('iso_datetime')
def iso_datetime(value, format='%B %-d, %Y at %-I:%M %p'):
    """TODO: Description."""
    from datetime import datetime
    
    if not value or value is None:
        return ''
    else:
        return datetime.strptime(value, '%Y-%m-%dT%H:%M:%S.%f').strftime(format)


@app.route('/orca/search', methods=['GET', 'POST'])
def search():
    """TODO: Description."""
    import time
    from orca.search import load_search_cache

    if request.method == 'POST':
        query_str = request.form['query']
        do_search.delay(query_str)
        time.sleep(3)
        return redirect(url_for('search'))

    search_index, _ = load_search_cache(batch_path)
    return render_template('search.html', searches=search_index)
