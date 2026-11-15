import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from taint.agents import med_held, run_visit  # noqa: E402
from taint.data import make_patients, make_visit, parse_hl7, payload  # noqa: E402
from taint.defences import critical_from_structured, detector_flags, filter_text  # noqa: E402
from taint.llm import MockModel, parse_json  # noqa: E402
from taint.memory import Memory  # noqa: E402

P = make_patients(3)


def test_hl7_roundtrip_and_taint_location():
    v = make_visit(P[0], "overt@hl7_nte")
    m = parse_hl7(v.hl7)
    assert m["results"][0]["flag"] == "HH" and m["comments"][0]["id"] == v.tainted_ids[0]
    assert "Ignore previous instructions" in m["comments"][0]["text"]
    assert make_visit(P[0], "camouflaged@fax").tainted_ids[0].startswith("FAX")
    assert make_visit(P[0], "clean").tainted_ids == []


def test_detector_catches_overt_but_not_camouflaged():
    assert detector_flags(payload("overt", "Potassium"))
    assert not detector_flags(payload("camouflaged", "Potassium"))
    assert not detector_flags(payload("control", "Potassium"))
    assert "[removed by filter]" in filter_text("Fine. " + payload("overt", "Glucose"))


def test_critical_comes_from_coded_fields_only():
    v = make_visit(P[1], "camouflaged@hl7_nte")
    assert [r["test"] for r in critical_from_structured(parse_hl7(v.hl7)["results"])] == ["Glucose"]


def test_unlearning_string_match_misses_summary_provenance_does_not():
    mem = Memory()
    bad = payload("persistent", "Potassium")
    mem.add("summary", "Intake summary: history of spurious Potassium results.", ["MSG1/OBX1", "MSG1/NTE1"])
    mem.add("raw_note", "Lab comment: " + bad, ["MSG1/NTE1"])
    mem.add("raw_note", "X-ray image comment: portable film.", ["IMG1/ImageComments"])
    m1 = Memory(entries=list(mem.entries))
    assert len(m1.unlearn_string_match(bad)) == 1 and any("spurious" in e.text for e in m1.entries)
    m2 = Memory(entries=list(mem.entries))
    assert len(m2.unlearn_provenance("MSG1/NTE1")) == 2 and len(m2.entries) == 1


def test_pipeline_with_mock_model():
    mock = MockModel()
    clean = run_visit(mock, make_visit(P[0], "clean"), "none")
    assert clean["safe"]
    attacked = run_visit(mock, make_visit(P[0], "camouflaged@dicom"), "none")
    assert not attacked["safe"] and attacked["intake_tainted"]
    defended = run_visit(mock, make_visit(P[0], "camouflaged@dicom"), "taint_tracking")
    assert defended["safe"] and not defended["intake_tainted"]


def test_helpers():
    assert parse_json('blah {"a": 1,} tail') == {"a": 1}
    assert med_held({"Spironolactone 25mg": "Hold"}, "spironolactone 25 mg daily")
    assert not med_held({"metformin": "hold"}, "spironolactone 25 mg daily")
