from src.infrastructure.adapters.xmltv_repository import XMLTVRepository


def test_load_epg_parses_xmltv_channels_programs_and_name_fallback(tmp_path):
    guide_path = tmp_path / "guide.xml"
    guide_path.write_bytes(
        b"""
        <tv>
          <channel id="news.id">
            <display-name>News HD</display-name>
          </channel>
          <programme channel="news.id" start="20260704100000 +0000" stop="20260704110000 +0000">
            <title>Morning News</title>
            <desc>Headlines and analysis</desc>
            <category>News</category>
          </programme>
          <programme channel="news.id" start="20260704113000 +0000" stop="20260704120000 +0000">
            <title>Midday News</title>
          </programme>
          <programme channel="missing-times">
            <title>Skipped</title>
          </programme>
        </tv>
        """
    )

    epg_data = XMLTVRepository().load_epg(str(guide_path))

    schedule = epg_data.get_programs_for_channel("news.id")
    assert [program.title for program in schedule] == ["Morning News", "Midday News"]
    assert schedule[0].description == "Headlines and analysis"
    assert schedule[0].category == "News"
    assert schedule[1].description == ""
    assert schedule[1].category == "Otros"
    assert schedule[0].start_time.year == 2026
    assert schedule[0].start_time.month == 7
    assert schedule[0].start_time.day == 4
    assert [
        program.title for program in epg_data.get_programs_by_normalized_name("newshd")
    ] == [
        "Morning News",
        "Midday News",
    ]


def test_load_epg_returns_empty_data_for_missing_file(tmp_path):
    epg_data = XMLTVRepository().load_epg(str(tmp_path / "missing.xml"))

    assert epg_data.programs == []


XMLTV_SAMPLE = b"""<tv>
  <channel id="c1">
    <display-name>Canal Uno</display-name>
  </channel>
  <programme channel="c1" start="20260704100000 +0000" stop="20260704110000 +0000">
    <title>Programa Comprimido</title>
  </programme>
</tv>
"""


def _assert_single_program(epg_data):
    assert [p.title for p in epg_data.programs] == ["Programa Comprimido"]
    assert [p.title for p in epg_data.get_programs_for_channel("c1")] == ["Programa Comprimido"]


def test_load_epg_from_gzip(tmp_path):
    import gzip

    guide = tmp_path / "guide.xml.gz"
    guide.write_bytes(gzip.compress(XMLTV_SAMPLE))

    epg_data = XMLTVRepository().load_epg(str(guide))

    _assert_single_program(epg_data)


def test_load_epg_from_zip(tmp_path):
    import io
    import zipfile

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("guide.xml", XMLTV_SAMPLE)

    guide = tmp_path / "guide.zip"
    guide.write_bytes(buf.getvalue())

    epg_data = XMLTVRepository().load_epg(str(guide))

    _assert_single_program(epg_data)


def test_load_epg_from_7z(tmp_path):
    from pathlib import Path
    from unittest import mock

    def _fake_extract_7z(archive, dest_dir, targets=None):
        Path(dest_dir, "guide.xml").write_bytes(XMLTV_SAMPLE)

    guide = tmp_path / "guide.7z"
    guide.write_bytes(b"fake-7z-archive")

    with mock.patch(
        "src.infrastructure.adapters.xmltv_repository.extract_7z",
        side_effect=_fake_extract_7z,
    ):
        epg_data = XMLTVRepository().load_epg(str(guide))

    _assert_single_program(epg_data)
