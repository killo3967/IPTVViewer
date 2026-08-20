from datetime import datetime, timedelta

from src.application.services.epg_manager import EPGManager
from src.domain.entities.epg import EPGData, Program, normalize_name
from src.domain.ports.i_epg_repo import IEPGRepository


class FakeEPGRepository(IEPGRepository):
    def __init__(self, epg_data):
        self.epg_data = epg_data
        self.sources = []

    def load_epg(self, source):
        self.sources.append(source)
        return self.epg_data


def make_program(title, channel_id, starts_in_minutes, ends_in_minutes):
    now = datetime.now()
    return Program(
        title=title,
        start_time=now + timedelta(minutes=starts_in_minutes),
        end_time=now + timedelta(minutes=ends_in_minutes),
        channel_id=channel_id,
    )


def test_normalize_name_removes_case_spaces_and_punctuation():
    assert normalize_name("  La 1 HD+ ") == "la1hd"
    assert normalize_name("") == ""


def test_update_epg_loads_source_and_exposes_has_data():
    current = make_program("Current News", "news.id", -5, 55)
    epg_data = EPGData([current], {"news.id": "News Channel"})
    repository = FakeEPGRepository(epg_data)
    manager = EPGManager(repository)

    manager.update_epg("guide.xml")

    assert repository.sources == ["guide.xml"]
    assert manager.has_data


def test_update_epg_ignores_empty_source():
    repository = FakeEPGRepository(EPGData([make_program("Current", "id", -5, 55)]))
    manager = EPGManager(repository)

    manager.update_epg("")

    assert repository.sources == []
    assert not manager.has_data


def test_get_currently_airing_uses_id_then_normalized_name_fallback():
    current = make_program("Current Sports", "sports.real.id", -10, 10)
    past = make_program("Old Sports", "sports.real.id", -60, -30)
    epg_data = EPGData([past, current], {"sports.real.id": "Sports HD"})
    manager = EPGManager(FakeEPGRepository(epg_data))
    manager.update_epg("guide.xml")

    by_id = manager.get_currently_airing("sports.real.id")
    by_name = manager.get_currently_airing("missing.id", "Sports-HD")

    if by_id is None or by_name is None:
        raise AssertionError("Expected current EPG programs by id and fallback name")

    assert by_id.title == "Current Sports"
    assert by_name.title == "Current Sports"


def test_get_program_schedule_sorts_programs_and_falls_back_by_normalized_name():
    later = make_program("Later Movie", "movies.id", 60, 120)
    earlier = make_program("Earlier Movie", "movies.id", 0, 30)
    epg_data = EPGData([later, earlier], {"movies.id": "Movies Channel"})
    manager = EPGManager(FakeEPGRepository(epg_data))
    manager.update_epg("guide.xml")

    schedule = manager.get_program_schedule("missing.id", "Movies-Channel")

    assert [program.title for program in schedule] == ["Earlier Movie", "Later Movie"]
    assert manager.get_program_schedule("", "") == []
