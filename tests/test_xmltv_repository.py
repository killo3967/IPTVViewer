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
