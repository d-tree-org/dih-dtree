import json

import pytest

from dihlibs.jsonq import JsonQ


@pytest.fixture
def sample_document():
    return {
        "name": "John",
        "age": 30,
        "person": {
            "name": "John",
            "address": {"city": "New York", "zip": "10001"},
            "contacts": [{"city": "Boston"}, {"city": "Denver"}],
        },
        "people": [
            {"name": "John"},
            {"name": "Jane"},
            {"name": "Doe"},
        ],
        "items": [
            {"name": "item1", "value": 10, "date": "2020-01-02"},
            {"name": "item2", "value": 20, "date": "02-01-2020"},
            {"name": "item3", "value": 30, "date": "2020-01-04"},
        ],
        "numbers": list(range(10)),
        "misc": {"data": {"items": [{"id": 1, "name": "item1"}, {"id": 2, "name": "item2"}]}},
        "entries": [{"flag": "yes"}, {"flag": "no"}, {"flag": "ndiyo"}],
        "measurements": [{"value": "10"}, {"value": "20"}, {"value": "x"}],
        "wild": {"matchOne": 1, "matchTwo": 2, "miss": 3},
    }


@pytest.fixture
def sample_jsonq(sample_document):
    return JsonQ(sample_document)


class _DummyResponseSuccess:
    def json(self):
        return {"status": "ok"}


class _DummyResponseFallback:
    text = '{"raw": "payload"}'

    def json(self):
        raise ValueError("not json")


def test_from_response_when_json_available():
    assert JsonQ.from_response(_DummyResponseSuccess()).root == {"status": "ok"}


def test_from_response_falls_back_to_text():
    assert JsonQ.from_response(_DummyResponseFallback()).root == '{"raw": "payload"}'


def test_get_with_simple_json(sample_jsonq):
    result = sample_jsonq.get("name")
    assert result.val() == "John"

    result = sample_jsonq.get("age")
    assert result.val() == 30


def test_get_with_nested_json(sample_jsonq):
    assert sample_jsonq.get("person.name").val() == "John"
    assert sample_jsonq.get("person.address.city").val() == "New York"
    assert sample_jsonq.get("person.address.zip").val() == "10001"


def test_get_with_array_json(sample_jsonq):
    assert sample_jsonq.get("people[0].name").val() == "John"
    assert sample_jsonq.get("people[1].name").val() == "Jane"
    assert sample_jsonq.get("people[2].name").val() == "Doe"


def test_get_with_wildcard_json(sample_jsonq):
    names = sample_jsonq.get("items[*].name").val()
    assert names == ["item1", "item2", "item3"]

    values = sample_jsonq.get("items[*].value").val()
    assert values == [10, 20, 30]


def test_get_with_deeply_nested_json():
    json_q = JsonQ({"a": {"b": {"c": {"d": {"e": "value"}}}}})
    assert json_q.get("a.b.c.d.e").val() == "value"


def test_get_with_mixed_content_json(sample_jsonq):
    assert sample_jsonq.get("misc.data.items[0].name").val() == "item1"
    assert sample_jsonq.get("misc.data.items[1].name").val() == "item2"


def test_get_with_non_existing_path(sample_jsonq):
    result = sample_jsonq.get("nonExisting")
    assert result.is_empty()
    assert result.val() is None


def test_get_with_special_characters_in_keys():
    json_q = JsonQ({"na.me": "John", "a-ge": 30})
    assert json_q.get('["na.me"]').val() == "John"
    assert json_q.get('["a-ge"]').val() == 30


def test_get_with_array_slices(sample_jsonq):
    assert sample_jsonq.get("numbers[:3]").val() == [0, 1, 2]
    assert sample_jsonq.get("numbers[7:]").val() == [7, 8, 9]


def test_get_with_filter_expression(sample_jsonq):
    result = sample_jsonq.get("items[?(@.value > 15)].name")
    assert result.val() == ["item2", "item3"]


def test_recursive_wildcard_paths(sample_jsonq):
    cities = sample_jsonq.get("..city").val()
    assert set(cities) == {"New York", "Boston", "Denver"}
    assert sample_jsonq.get("...zip").val() == "10001"


def test_globbed_path_matches_keys(sample_jsonq):
    assert sample_jsonq.get("wild.match*").val() == [1, 2]


def test_array_slices_with_negative_indices_and_unions(sample_jsonq):
    assert sample_jsonq.get("numbers[-2:]").val() == [8, 9]
    assert sample_jsonq.get("numbers[1:4,7:]").val() == [1, 2, 3, 7, 8, 9]
    assert sample_jsonq.get("numbers[0,2,4]").val() == [0, 2, 4]


def test_filter_with_regex_expression():
    data = {
        "items": [
            {"name": "item-alpha", "value": 10},
            {"name": "skip", "value": 20},
            {"name": "item-beta", "value": 30},
        ]
    }
    result = JsonQ(data).get("items[?(@.name~'item.*')].value")
    assert result.val() == [10, 30]


def test_filter_accepts_double_quotes(sample_jsonq):
    result = sample_jsonq.get('items[?(@.name=="item2")].value')
    assert result.val() == 20


def test_filter_interprets_boolean_like_strings(sample_jsonq):
    filtered = sample_jsonq.get("entries[?(@.flag)]").val()
    assert [entry["flag"] for entry in filtered] == ["yes", "ndiyo"]


def test_value_str_and_int_helpers(sample_jsonq):
    assert sample_jsonq.value("items[0].value") == 10
    assert sample_jsonq.str("items[*].name") == '["item1", "item2", "item3"]'

    numbers = JsonQ({"numbers": ["1", "2", "3"]})
    assert numbers.int("numbers[0]") == 1


def test_integers_helper(sample_jsonq):
    assert sample_jsonq.integers("items[*].value") == [10, 20, 30]


def test_select_with_alias(sample_jsonq):
    selection = sample_jsonq.get("items").select("name", "value as amount").root
    assert selection == [
        {"name": "item1", "amount": 10},
        {"name": "item2", "amount": 20},
        {"name": "item3", "amount": 30},
    ]


def test_where_filters_items(sample_jsonq):
    result = sample_jsonq.get("items").where("@.value > ?", 15).root
    assert result == [
        {"name": "item2", "value": 20, "date": "02-01-2020"},
        {"name": "item3", "value": 30, "date": "2020-01-04"},
    ]


def test_change_updates_value(sample_jsonq):
    sample_jsonq.change("person.address.city", lambda city: city.upper())
    assert sample_jsonq.get("person.address.city").val() == "NEW YORK"


def test_put_overrides_dictionary_value(sample_jsonq):
    sample_jsonq.put("person.address.zip", "20002")
    assert sample_jsonq.get("person.address.zip").val() == "20002"


def test_add_appends_to_list():
    data = {"items": [1, 2]}
    jq = JsonQ(data)
    jq.add("items", 3)
    assert jq.root["items"] == [1, 2, 3]


def test_add_appends_to_all_matched_lists():
    data = {"items": [[1], [2]]}
    jq = JsonQ(data)
    jq.add("items[*]", 3)
    assert jq.root["items"] == [[1, 3], [2, 3]]


def test_add_falls_back_to_put_for_missing_targets():
    data = {"items": {"a": [1]}}
    jq = JsonQ(data)
    jq.add("items.b", 9)
    assert jq.root["items"]["b"] == 9


def test_merge_merges_existing_dict():
    data = {"person": {"name": "John", "address": {"city": "New York"}}}
    jq = JsonQ(data)
    jq.merge("person.address", {"zip": "10001"})
    assert jq.root["person"]["address"] == {"city": "New York", "zip": "10001"}


def test_merge_extends_list_by_default():
    data = {"items": [1, 2]}
    jq = JsonQ(data)
    jq.merge("items", [3, 4])
    assert jq.root["items"] == [1, 2, 3, 4]


def test_merge_handles_multiple_list_matches():
    data = {"items": [{"tags": [1]}, {"tags": [2]}]}
    jq = JsonQ(data)
    jq.merge("items[*].tags", [3])
    assert jq.root["items"] == [{"tags": [1, 3]}, {"tags": [2, 3]}]


def test_merge_replace_policy_replaces_lists():
    data = {"items": [1, 2, 3]}
    jq = JsonQ(data)
    jq.merge("items", [9], list_policy="replace")
    assert jq.root["items"] == [9]


def test_merge_many_updates_multiple_targets():
    data = {"queries": [{"filters": [1]}, {"filters": [2]}]}
    jq = JsonQ(data)
    jq.merge_many(
        {
            "queries[*].filters": [3],
            "result_format": "csv",
            "result_type": "full",
        }
    )
    assert jq.root["queries"] == [{"filters": [1, 3]}, {"filters": [2, 3]}]
    assert jq.root["result_format"] == "csv"
    assert jq.root["result_type"] == "full"


def test_merge_many_respects_list_policy():
    data = {"items": [1, 2, 3]}
    jq = JsonQ(data)
    jq.merge_many({"items": [9, 8]}, list_policy="replace")
    assert jq.root["items"] == [9, 8]


def test_keys_and_leaves(sample_jsonq):
    keys = set(sample_jsonq.keys("person", trimmed=True))
    assert keys == {"name", "city", "zip"}

    leaves = sample_jsonq.leaves("person")
    assert leaves["person.address.city"] == "New York"
    assert leaves["person.address.zip"] == "10001"
    assert leaves["person.contacts.0.city"] == "Boston"
    assert leaves["person.contacts.1.city"] == "Denver"


def test_leaves_with_predicate(sample_jsonq):
    only_ids = sample_jsonq.leaves(
        "misc", predicateFunc=lambda path, value: path.endswith("id")
    )
    assert only_ids == {"misc.data.items.0.id": 1, "misc.data.items.1.id": 2}


def test_for_each_visits_all_items(sample_jsonq):
    items = []
    sample_jsonq.get("items").for_each(lambda idx, node: items.append((idx, node.val())))
    assert items == [
        ("0", {"name": "item1", "value": 10, "date": "2020-01-02"}),
        ("1", {"name": "item2", "value": 20, "date": "02-01-2020"}),
        ("2", {"name": "item3", "value": 30, "date": "2020-01-04"}),
    ]


def test_is_empty_and_val():
    assert JsonQ({}).is_empty()
    assert JsonQ([]).is_empty()
    assert JsonQ("").is_empty()
    assert JsonQ([]).val() is None
    assert JsonQ({"data": 1}).val() == {"data": 1}


def test_to_string_round_trips_json(sample_jsonq):
    serialized = sample_jsonq.get("people").to_string()
    assert json.loads(serialized) == [{"name": "John"}, {"name": "Jane"}, {"name": "Doe"}]


def test_get_dates_parses_known_formats(sample_jsonq):
    dates = sample_jsonq.get("items").date_column("date")
    as_strings = sorted(dt.strftime("%Y-%m-%d") for dt in dates)
    assert as_strings == ["2020-01-02", "2020-01-02", "2020-01-04"]


def test_find_returns_empty_for_primitives():
    assert JsonQ(5)._find("anything") == []
