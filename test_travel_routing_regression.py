from mc_paths import classify_keyword, resolve_chain_type
from chain_deriver import _apply_cuap_titles

def u(*xs):
    return ''.join(chr(x) for x in xs)

def test_chestertons_naksan_is_travel_not_medicine():
    seed = u(52404,49828,53552,53668,49828,32,45209,49328)
    assert classify_keyword(seed) == 'travel'
    assert resolve_chain_type(seed) == 'lateral'

def test_title_gate_does_not_inject_english_template_fragments():
    seed = u(52404,49828,53552,53668,49828,32,45209,49328)
    posts = [{'title': seed + ' overview', 'target_keyword': seed, 'key_points': [u(45209,49328,51032,51060,32,51221,51228,49345,51228)], 'angle': 'overview'}]
    result = _apply_cuap_titles(seed, posts)
    assert 'before use' not in result[0]['title']
    assert 'practical guide' not in result[0]['title']
    assert result[0]['title'] == posts[0]['title']
