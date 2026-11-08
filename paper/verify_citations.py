"""Fetch bibliographic records for every candidate citation from Crossref (DOIs) and arXiv (IDs).

Writes paper/citations_verified.json: the metadata the registries returned, unedited, with the date fetched.
A citation goes into refs.bib only if it appears here, and only with what the registry says.
Run: python paper/verify_citations.py
"""
import json
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent / 'citations_verified.json'
AGENT = {'User-Agent': 'ota-campaign-verifier-citation-check/1.0'}
DOIS = {
    'konnov2019': '10.1145/3360549',
    'clarke1989': '10.1109/LICS.1989.39190',
    'hagen2025': '10.1016/j.cose.2025.104751',
    'lorch2024': '10.1145/3678890.3678927',
    'kuppusamy2018': '10.1109/MVT.2017.2778751',
    'kirk2021': '10.1109/QRS-C55045.2021.00124',
    'kirk2023': '10.1016/j.jlamp.2022.100812',
    'ponsard2021': '10.5220/0010431408000808',
    'samuel2010': '10.1145/1866307.1866315',
    'lamport1994': '10.1145/177492.177726',
    'clarke1994': '10.1145/186025.186051',
    'newcombe2015': '10.1145/2699417',
    'cousineau2012': '10.1007/978-3-642-32759-9_14',
    'abadi1991': '10.1016/0304-3975(91)90224-P',
    'otasurvey2024': '10.1007/s10462-024-10968-z',
    'yu1999': '10.1007/3-540-48153-2_6',
    'emerson1995': '10.1145/199448.199468',
    'pedroza2011': '10.1109/VETECF.2011.6093061',
    'mukherjee2021': '10.14722/autosec.2021.23028',
    'idrees2011': '10.1007/978-3-642-19786-4_20',
    'boureanu2023': '10.1109/SMC53992.2023.10394216',
    'mahmood2020': '10.1109/ICSTW50294.2020.00019',
    'mahmood2022': '10.1016/j.vehcom.2022.100468',
}
ARXIV = {
    'cirstea2024': '2404.16075',
    'howard2024': '2406.17455',
    'schmid2021': '2101.07307',
    'shoker2023': '2307.02032',
    'hagen2025arxiv': '2511.15479',
    'autosarfota2025': '2503.05839',
    'sdvsurvey2026': '2605.30001',
}
SEARCHES: dict[str, str] = {}


def get(url: str) -> bytes:
    request = urllib.request.Request(url, headers=AGENT)
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def crossref(message: dict) -> dict:
    return {
        'doi': message.get('DOI'),
        'title': (message.get('title') or [''])[0],
        'container': (message.get('container-title') or [''])[0],
        'event': (message.get('event') or {}).get('name'),
        'issued': (message.get('issued') or {}).get('date-parts'),
        'volume': message.get('volume'), 'issue': message.get('issue'), 'page': message.get('page'),
        'article_number': message.get('article-number'), 'publisher': message.get('publisher'),
        'type': message.get('type'),
        'authors': [' '.join(filter(None, (a.get('given'), a.get('family')))) or a.get('name', '') for a in message.get('author', [])],
        'editors': [' '.join(filter(None, (a.get('given'), a.get('family')))) for a in message.get('editor', [])],
        'series': message.get('container-title', [None])[1:] or None,
        'isbn': message.get('ISBN'),
    }


def main() -> None:
    records: dict[str, dict] = {'fetched_utc': datetime.now(timezone.utc).isoformat(), 'crossref': {}, 'arxiv': {}, 'search': {}}
    for key, doi in DOIS.items():
        try:
            message = json.loads(get('https://api.crossref.org/works/' + urllib.parse.quote(doi)))['message']
            records['crossref'][key] = crossref(message)
        except Exception as error:  # Recorded, so a missing record is visible rather than silently dropped.
            records['crossref'][key] = {'doi': doi, 'error': repr(error)}
        time.sleep(0.3)
    feed = ET.fromstring(get('https://export.arxiv.org/api/query?max_results=50&id_list=' + ','.join(ARXIV.values())))
    ns = {'a': 'http://www.w3.org/2005/Atom', 'x': 'http://arxiv.org/schemas/atom'}
    by_id = {}
    for entry in feed.findall('a:entry', ns):
        identifier = entry.find('a:id', ns).text.rsplit('/', 1)[-1].split('v')[0]
        journal, doi = entry.find('x:journal_ref', ns), entry.find('x:doi', ns)
        by_id[identifier] = {
            'id': identifier, 'title': ' '.join(entry.find('a:title', ns).text.split()),
            'published': entry.find('a:published', ns).text[:10], 'updated': entry.find('a:updated', ns).text[:10],
            'authors': [a.find('a:name', ns).text for a in entry.findall('a:author', ns)],
            'journal_ref': journal.text if journal is not None else None, 'doi': doi.text if doi is not None else None,
            'summary': ' '.join(entry.find('a:summary', ns).text.split()),
        }
    for key, identifier in ARXIV.items():
        records['arxiv'][key] = by_id.get(identifier, {'id': identifier, 'error': 'not returned'})
    for key, query in SEARCHES.items():
        items = json.loads(get('https://api.crossref.org/works?rows=3&query.bibliographic=' + urllib.parse.quote(query)))['message']['items']
        records['search'][key] = [crossref(item) for item in items]
    OUT.write_text(json.dumps(records, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
    errors = [k for section in ('crossref', 'arxiv') for k, v in records[section].items() if 'error' in v]
    print(f'wrote {OUT.name}; errors: {errors}')


if __name__ == '__main__':
    main()
