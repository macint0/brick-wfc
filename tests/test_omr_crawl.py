"""The OMR crawler (M12e): index and set-page parsing, resumable crawl, polite retries. No network."""
import io
import json
import urllib.error
from pathlib import Path

import pytest

from brickwfc.ldraw.omr_crawl import (SET_URL, SETS_URL, OmrModel, PoliteClient, crawl, main, parse_set_page,
                                      parse_sets_page)


def _row(record: int, number: str, name: str, theme: str, year: str, count: str) -> str:
    cells = {"image": "", "number": number, "name": name, "theme.name": theme, "year": year, "models_count": count}
    return "".join(
        f'<td wire:key="X.table.record.{record}.column.{col}" class="fi-ta-cell"><a href="https://library.ldraw.org/omr/'
        f'sets/{record}"><div class="fi-ta-text">{value}</div></a></td>' for col, value in cells.items())


def _sets_page(rows: list[tuple], last: int) -> str:
    pager = "".join(f"<button wire:click=\"gotoPage({p}, &#039;page&#039;)\">{p}</button>" for p in range(1, last + 1))
    return "<table>" + "".join(f"<tr>{_row(*r)}</tr>" for r in rows) + "</table>" + pager


def _model(name: str, author: str, file: str, missing: str = "No") -> str:
    return (f'<div class="flex flex-col rounded border"><div class="font-bold bg-gray-200 p-2"> {name} </div>'
            f'<div class="p-2"><span class="font-bold pr-2">Author:</span>{author} </div>'
            f'<div class="grid grid-cols-3 p-2"><div><span class="font-bold">Missing Parts</span><br> {missing} </div>'
            f'<div><span class="font-bold">Missing Patterns</span><br> No </div>'
            f'<div><span class="font-bold">Missing Stickers</span><br> Yes </div></div>'
            f'<a class="rounded-lg" href="https://library.ldraw.org/library/omr/{file}">Download</a></div>')


SITE = {
    SETS_URL.format(page=1): _sets_page([(7, "6378-1", "Shell Service Station", "Classic Town", "1986", "1")], 2),
    SETS_URL.format(page=2): _sets_page([(9, "8094-1", "Control Centre &amp; Co", "Technic", "1990", "2")], 2),
    SET_URL.format(id=7): _model("Main Model", "A [a]", "6378-1.mpd"),
    SET_URL.format(id=9): _model("Robotic Arm", "B [b]", "8094-1_Robotic-Arm.mpd", "Yes")
    + _model("Plotter", "B [b]", "8094-1_Plotter.mpd"),
    "https://library.ldraw.org/library/omr/6378-1.mpd": "0 FILE a",
    "https://library.ldraw.org/library/omr/8094-1_Robotic-Arm.mpd": "0 FILE b",
    "https://library.ldraw.org/library/omr/8094-1_Plotter.mpd": "0 FILE c",
}


class FakeSite:
    def __init__(self, pages: dict[str, str]) -> None:
        self.pages, self.calls = pages, []

    def get(self, url: str) -> bytes:
        self.calls.append(url)
        if url not in self.pages:
            raise urllib.error.HTTPError(url, 404, "Not Found", None, None)  # type: ignore[arg-type]
        return self.pages[url].encode("utf-8")


def test_parse_sets_page_reads_rows_and_last_page() -> None:
    sets, last = parse_sets_page(SITE[SETS_URL.format(page=2)])
    assert last == 2
    assert [(s.id, s.number, s.name, s.theme, s.year, s.models_count) for s in sets] == [
        (9, "8094-1", "Control Centre & Co", "Technic", 1990, 2)]


def test_parse_set_page_reads_every_model_in_order() -> None:
    models = parse_set_page(SITE[SET_URL.format(id=9)])
    assert [m.file for m in models] == ["8094-1_Robotic-Arm.mpd", "8094-1_Plotter.mpd"]
    assert models[0] == OmrModel("Robotic Arm", "B [b]", "8094-1_Robotic-Arm.mpd", True, False, True)
    assert models[0].url == "https://library.ldraw.org/library/omr/8094-1_Robotic-Arm.mpd"


def test_crawl_downloads_every_model_and_resumes(tmp_path: Path) -> None:
    site = FakeSite(SITE)
    (tmp_path / "6378-1.mpd").write_text("already here", encoding="utf-8")
    sets, counts = crawl(tmp_path, site.get, log=lambda s: None)
    assert counts == {"sets": 2, "models": 3, "on_disk": 3, "downloaded": 2, "failed": 0}
    assert (tmp_path / "6378-1.mpd").read_text(encoding="utf-8") == "already here"  # existing files are kept
    assert (tmp_path / "8094-1_Plotter.mpd").read_text(encoding="utf-8") == "0 FILE c"
    index = json.loads((tmp_path / "index.json").read_text(encoding="utf-8"))
    assert [m["file"] for s in index for m in s["models"]] == ["6378-1.mpd", "8094-1_Robotic-Arm.mpd", "8094-1_Plotter.mpd"]
    again = FakeSite(SITE)
    _, counts = crawl(tmp_path, again.get, log=lambda s: None)
    assert again.calls == [] and counts["downloaded"] == 0  # index, set pages and models all cached


def test_crawl_resumes_set_pages_after_a_crash(tmp_path: Path) -> None:
    pages = dict(SITE)
    del pages[SET_URL.format(id=9)]
    with pytest.raises(urllib.error.HTTPError):
        crawl(tmp_path, FakeSite(pages).get, log=lambda s: None)
    site = FakeSite(SITE)
    sets, counts = crawl(tmp_path, site.get, log=lambda s: None)
    assert SET_URL.format(id=7) not in site.calls and SET_URL.format(id=9) in site.calls
    assert counts["models"] == 3


def test_crawl_records_a_missing_model_file(tmp_path: Path) -> None:
    pages = dict(SITE)
    del pages["https://library.ldraw.org/library/omr/8094-1_Plotter.mpd"]
    _, counts = crawl(tmp_path, FakeSite(pages).get, log=lambda s: None)
    assert counts["failed"] == 1 and counts["on_disk"] == 2
    assert "8094-1_Plotter.mpd: HTTP 404" in (tmp_path / "crawl_failures.txt").read_text(encoding="utf-8")
    crawl(tmp_path, FakeSite(pages).get, download=False, log=lambda s: None)  # an index-only rerun keeps the list
    assert "8094-1_Plotter.mpd: HTTP 404" in (tmp_path / "crawl_failures.txt").read_text(encoding="utf-8")


def test_a_model_listed_twice_on_its_set_page_is_kept_once(tmp_path: Path) -> None:
    pages = dict(SITE)
    pages[SET_URL.format(id=7)] = SITE[SET_URL.format(id=7)] * 2  # as on the OMR's 6608-1 page
    sets, counts = crawl(tmp_path, FakeSite(pages).get, log=lambda s: None)
    assert [m.file for m in sets[0].models] == ["6378-1.mpd"] and counts["models"] == 3


class _Response(io.BytesIO):
    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def test_polite_client_retries_transient_errors_and_sends_a_user_agent() -> None:
    sleeps: list[float] = []
    seen: list[str] = []
    outcomes = [urllib.error.HTTPError("u", 503, "busy", None, None), urllib.error.URLError("reset"), b"ok"]  # type: ignore[arg-type]

    def opener(request, timeout):  # noqa: ANN001, ANN202
        seen.append(request.get_header("User-agent"))
        outcome = outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return _Response(outcome)

    client = PoliteClient(delay_s=0.0, retries=3, sleep=sleeps.append, opener=opener)
    assert client.get("https://example.invalid/x") == b"ok"
    assert client.requests == 3 and sleeps == [5.0, 10.0]
    assert all("brickwfc" in agent for agent in seen)


def test_polite_client_gives_up_on_a_permanent_error() -> None:
    def opener(request, timeout):  # noqa: ANN001, ANN202
        raise urllib.error.HTTPError("u", 404, "missing", None, None)  # type: ignore[arg-type]

    client = PoliteClient(delay_s=0.0, sleep=lambda s: None, opener=opener)
    with pytest.raises(urllib.error.HTTPError):
        client.get("https://example.invalid/x")
    assert client.requests == 1


def test_main_parses_its_arguments(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    seen = {}

    def fake_crawl(out, get, refresh, download, log):  # noqa: ANN001, ANN202
        seen.update(out=out, refresh=refresh, download=download)
        return [], {"sets": 0, "models": 0, "on_disk": 0, "downloaded": 0, "failed": 0}

    monkeypatch.setattr("brickwfc.ldraw.omr_crawl.crawl", fake_crawl)
    assert main(["--out", str(tmp_path), "--delay", "0", "--refresh", "--index-only"]) == 0
    assert seen == {"out": tmp_path, "refresh": True, "download": False}


def test_crawl_marks_main_models_and_alternates(tmp_path: Path) -> None:
    crawl(tmp_path, FakeSite(SITE).get, log=lambda s: None)
    index = json.loads((tmp_path / "index.json").read_text(encoding="utf-8"))
    marks = {m["file"]: m["main"] for s in index for m in s["models"]}
    # 8094-1 has no 8094-1.mpd: its first listed model is the main one
    assert marks == {"6378-1.mpd": True, "8094-1_Robotic-Arm.mpd": True, "8094-1_Plotter.mpd": False}
    lines = [json.loads(line) for line in (tmp_path / "index.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [m["main"] for s in lines for m in s["models"]] == [True, True, False]
