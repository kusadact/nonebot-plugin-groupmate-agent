from tests.helpers import load_module

reply_segments = load_module("groupmate_agent_reply_segments_under_test", "reply_segments.py")


def test_plain_newlines_are_kept_in_one_reply_segment():
    assert reply_segments.split_reply_segments("第一行\n第二行") == ["第一行\n第二行"]


def test_slash_n_separator_splits_multiple_reply_messages():
    assert reply_segments.split_reply_segments("第一条\n/n\n第二条\n/n\n第三条") == [
        "第一条",
        "第二条",
        "第三条",
    ]


def test_separator_must_be_on_its_own_line():
    assert reply_segments.split_reply_segments("路径 /n 不是分隔\n下一行") == ["路径 /n 不是分隔\n下一行"]


def test_newline_split_mode_keeps_multi_target_direct_reply_behavior():
    assert reply_segments.split_reply_segments(
        "回复一号\n回复二号",
        allow_reply_duplicates=True,
        split_on_newline=True,
    ) == ["回复一号", "回复二号"]


def test_duplicate_reply_segments_are_skipped_without_collapsing_message_newlines():
    assert reply_segments.split_reply_segments("哈\n哈\n/n\n哈\n哈") == ["哈\n哈"]


def test_extra_segments_are_folded_into_third_message():
    assert reply_segments.split_reply_segments("1\n/n\n2\n/n\n3\n/n\n4") == ["1", "2", "3\n4"]
