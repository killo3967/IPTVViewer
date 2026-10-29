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


def test_get_next_program_returns_the_first_program_starting_after_now():
    current = make_program("Current", "id", -10, 20)
    upcoming = make_program("Upcoming", "id", 20, 50)
    later = make_program("Later", "id", 50, 80)
    epg_data = EPGData([later, current, upcoming], {"id": "Some Channel"})
    manager = EPGManager(FakeEPGRepository(epg_data))
    manager.update_epg("guide.xml")

    next_program = manager.get_next_program("id")

    if next_program is None:
        raise AssertionError("Expected a next program")
    assert next_program.title == "Upcoming"


def test_get_next_program_ignores_programs_that_already_started():
    past = make_program("Past", "id", -120, -60)
    current = make_program("Current", "id", -10, 20)
    upcoming = make_program("Upcoming", "id", 25, 55)
    epg_data = EPGData([past, current, upcoming], {"id": "Some Channel"})
    manager = EPGManager(FakeEPGRepository(epg_data))
    manager.update_epg("guide.xml")

    next_program = manager.get_next_program("id")

    if next_program is None:
        raise AssertionError("Expected a next program")
    assert next_program.title == "Upcoming"


def test_get_next_program_returns_none_when_the_guide_ends():
    past = make_program("Past", "id", -120, -60)
    current = make_program("Current", "id", -10, 10)
    epg_data = EPGData([past, current], {"id": "Some Channel"})
    manager = EPGManager(FakeEPGRepository(epg_data))
    manager.update_epg("guide.xml")

    assert manager.get_next_program("id") is None


def test_get_next_program_falls_back_by_normalized_name_and_copes_with_empty_ids():
    upcoming = make_program("Upcoming News", "news.real.id", 30, 60)
    epg_data = EPGData([upcoming], {"news.real.id": "News HD"})
    manager = EPGManager(FakeEPGRepository(epg_data))
    manager.update_epg("guide.xml")

    by_name = manager.get_next_program("missing.id", "News-HD")

    if by_name is None:
        raise AssertionError("Expected a next program by normalized name")
    assert by_name.title == "Upcoming News"
    assert manager.get_next_program("", "") is None


def test_get_next_program_returns_after_a_gap_in_the_guide():
    current = make_program("Current", "id", -10, 10)
    after_gap = make_program("After Gap", "id", 90, 120)
    epg_data = EPGData([current, after_gap], {"id": "Some Channel"})
    manager = EPGManager(FakeEPGRepository(epg_data))
    manager.update_epg("guide.xml")

    next_program = manager.get_next_program("id")

    if next_program is None:
        raise AssertionError("Expected a next program even with a gap")
    assert next_program.title == "After Gap"



def test_get_current_and_next_returns_both_with_one_lookup():
    past = make_program("Past", "id", -120, -60)
    current = make_program("Current", "id", -10, 20)
    upcoming = make_program("Upcoming", "id", 20, 50)
    epg_data = EPGData([upcoming, past, current], {"id": "Some Channel"})
    manager = EPGManager(FakeEPGRepository(epg_data))
    manager.update_epg("guide.xml")

    current_program, next_program = manager.get_current_and_next("id")

    if current_program is None or next_program is None:
        raise AssertionError("Expected both current and next programs")
    assert current_program.title == "Current"
    assert next_program.title == "Upcoming"


def test_get_current_and_next_with_gap_has_next_but_no_current():
    upcoming = make_program("Upcoming", "id", 30, 60)
    epg_data = EPGData([upcoming], {"id": "Some Channel"})
    manager = EPGManager(FakeEPGRepository(epg_data))
    manager.update_epg("guide.xml")

    current_program, next_program = manager.get_current_and_next("id")

    assert current_program is None
    if next_program is None:
        raise AssertionError("Expected a next program despite the gap")
    assert next_program.title == "Upcoming"


def test_get_current_and_next_at_the_end_of_the_guide_has_no_next():
    current = make_program("Current", "id", -10, 10)
    epg_data = EPGData([current], {"id": "Some Channel"})
    manager = EPGManager(FakeEPGRepository(epg_data))
    manager.update_epg("guide.xml")

    current_program, next_program = manager.get_current_and_next("id")

    if current_program is None:
        raise AssertionError("Expected a current program")
    assert next_program is None
