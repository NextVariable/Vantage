from __future__ import annotations

import json
from typing import Mapping

from sourceglint.connectors._http import HttpResponse
from sourceglint.connectors.scholarly import (
    ClinicalTrialsAdapter,
    DataCiteAdapter,
    DoajAdapter,
    InternetArchiveAdapter,
    OpenLibraryAdapter,
    PubMedAdapter,
    ZenodoAdapter,
)

REQUEST = {
    "query": "vector database",
    "query_language": "en",
    "market": "global",
    "retrieved_at": "2026-11-24T00:00:00Z",
    "limit": 5,
}
PLAN = {"time_window": {"days": 30}}


class StubHttp:
    user_agent = "test"

    def __init__(self, payloads: Mapping[str, object]):
        self.payloads = payloads
        self.calls: list[str] = []

    def request(self, url: str, *, headers: Mapping[str, str] | None = None, **kwargs):
        self.calls.append(url)
        for marker, payload in self.payloads.items():
            if marker in url:
                return HttpResponse(status=200, body=json.dumps(payload).encode(), url=url)
        raise AssertionError(f"unexpected url {url}")


def test_pubmed_uses_pubdate_and_keeps_epubdate_separate():
    http = StubHttp({
        "esearch.fcgi": {"esearchresult": {"idlist": ["111"]}},
        "esummary.fcgi": {"result": {
            "uids": ["111"],
            "111": {
                "uid": "111",
                "title": "Vector databases for retrieval.",
                "pubdate": "2026 Nov 23",
                "epubdate": "2026 Nov 20",
                "source": "J Test",
                "volume": "3",
                "issue": "2",
                "authors": [{"name": "Doe J"}, {"name": "Roe R"}],
            },
        }},
    })
    out = PubMedAdapter(http_client=http).retrieve(PLAN, REQUEST)
    assert out[0].url == "https://pubmed.ncbi.nlm.nih.gov/111/"
    assert out[0].published_at == "2026-11-23T00:00:00Z"
    assert out[0].raw_metadata["epubdate"] == "2026 Nov 20"
    assert out[0].raw_metadata["date_semantics"] == "journal_publication_date"
    assert out[0].author == "Doe J, Roe R"
    assert "mindate=2026-10-25" in http.calls[0]


def test_pubmed_month_precision_is_labelled():
    http = StubHttp({
        "esearch.fcgi": {"esearchresult": {"idlist": ["222"]}},
        "esummary.fcgi": {"result": {"222": {"uid": "222", "title": "T", "pubdate": "2026 Nov"}}},
    })
    out = PubMedAdapter(http_client=http).retrieve(PLAN, REQUEST)
    assert out[0].published_at == "2026-11-01T00:00:00Z"
    assert out[0].raw_metadata["date_precision"] == "month"


def test_doaj_uses_journal_month_and_fulltext_link():
    http = StubHttp({"doaj.org": {"results": [{
        "id": "abc123",
        "created_date": "2026-11-01T00:00:00Z",
        "bibjson": {
            "title": "Open access vectors",
            "abstract": "<p>Full abstract.</p>",
            "year": 2026,
            "month": "november",
            "author": [{"name": "Ada Lovelace"}],
            "journal": {"title": "OA Journal", "issns": ["1234-5678"]},
            "link": [{"url": "https://oa.example/article/1", "type": "fulltext"}],
        },
    }]}})
    out = DoajAdapter(http_client=http).retrieve(PLAN, REQUEST)
    assert out[0].url == "https://oa.example/article/1"
    assert out[0].published_at == "2026-11-01T00:00:00Z"
    assert out[0].text == "Full abstract."
    assert out[0].raw_metadata["date_semantics"] == "journal_publication_month"


def test_zenodo_prefers_publication_date_over_created():
    http = StubHttp({"zenodo.org": {"hits": {"hits": [{
        "id": 42,
        "doi": "10.5281/zenodo.42",
        "doi_url": "https://doi.org/10.5281/zenodo.42",
        "created": "2026-11-01T00:00:00Z",
        "updated": "2026-11-02T00:00:00Z",
        "metadata": {
            "title": "Dataset",
            "description": "<p>Records.</p>",
            "publication_date": "2026-03-04",
            "creators": [{"name": "Doe, J"}],
            "resource_type": {"type": "dataset", "title": "Dataset"},
        },
    }]}}})
    out = ZenodoAdapter(http_client=http).retrieve(PLAN, REQUEST)
    assert out[0].published_at == "2026-03-04T00:00:00Z"
    assert out[0].raw_metadata["date_semantics"] == "record_publication_date"
    assert out[0].text == "Records."


def test_datacite_falls_back_to_doi_created_and_labels_it():
    http = StubHttp({"api.datacite.org": {"data": [{
        "id": "10.9999/abc",
        "attributes": {
            "doi": "10.9999/abc",
            "titles": [{"title": "Vector data"}],
            "creators": [{"name": "Roe, R"}],
            "published": None,
            "issued": None,
            "created": "2026-05-06T07:08:09Z",
            "registered": "2026-05-07T00:00:00Z",
            "url": "https://repo.example/record/1",
            "types": {"resourceTypeGeneral": "Dataset"},
            "descriptions": [{"descriptionType": "Abstract", "description": "Summary."}],
        },
    }]}})
    out = DataCiteAdapter(http_client=http).retrieve(PLAN, REQUEST)
    assert out[0].url == "https://repo.example/record/1"
    assert out[0].published_at == "2026-05-06T07:08:09Z"
    assert out[0].raw_metadata["date_semantics"] == "doi_created"


def test_openlibrary_reports_year_precision():
    http = StubHttp({"openlibrary.org": {"docs": [{
        "key": "/works/OL1W",
        "title": "Vector Databases",
        "first_publish_year": 2025,
        "author_name": ["A. Author"],
    }]}})
    out = OpenLibraryAdapter(http_client=http).retrieve(PLAN, REQUEST)
    assert out[0].url == "https://openlibrary.org/works/OL1W"
    assert out[0].published_at == "2025-01-01T00:00:00Z"
    assert out[0].raw_metadata["date_precision"] == "year"


def test_internet_archive_uses_item_date():
    http = StubHttp({"archive.org": {"response": {"docs": [{
        "identifier": "item-1",
        "title": ["Archived report"],
        "date": "2019-07-01",
        "creator": "Collector",
    }]}}})
    out = InternetArchiveAdapter(http_client=http).retrieve(PLAN, REQUEST)
    assert out[0].url == "https://archive.org/details/item-1"
    assert out[0].published_at == "2019-07-01T00:00:00Z"
    assert out[0].raw_metadata["date_semantics"] == "archive_item_date"


def test_clinicaltrials_uses_first_posted_date():
    http = StubHttp({"clinicaltrials.gov": {"studies": [{
        "protocolSection": {
            "identificationModule": {"nctId": "NCT123", "briefTitle": "Trial"},
            "statusModule": {
                "overallStatus": "Recruiting",
                "studyFirstPostDateStruct": {"date": "2025-01-02"},
                "lastUpdatePostDateStruct": {"date": "2026-02-03"},
            },
            "descriptionModule": {"briefSummary": "Summary."},
            "sponsorCollaboratorsModule": {"leadSponsor": {"name": "Sponsor"}},
        },
    }]}})
    out = ClinicalTrialsAdapter(http_client=http).retrieve(PLAN, REQUEST)
    assert out[0].url == "https://clinicaltrials.gov/study/NCT123"
    assert out[0].published_at == "2025-01-02T00:00:00Z"
    assert out[0].raw_metadata["last_update_posted"] == "2026-02-03T00:00:00Z"
    assert out[0].author == "Sponsor"


def test_pubmed_returns_empty_for_no_hits():
    http = StubHttp({"esearch.fcgi": {"esearchresult": {"idlist": []}}})
    assert PubMedAdapter(http_client=http).retrieve(PLAN, REQUEST) == []
