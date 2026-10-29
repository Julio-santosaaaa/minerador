from minerador.slicing import slice_for_job

KW = [f"kw{i}" for i in range(23)]


def test_slices_are_disjoint_and_complete():
    parts = [slice_for_job(KW, j, 4) for j in range(4)]
    flat = [k for p in parts for k in p]
    assert sorted(flat) == sorted(KW) and len(flat) == len(set(flat))


def test_slice_is_stable_across_calls():
    assert slice_for_job(KW, 1, 4) == slice_for_job(KW, 1, 4)


def test_empty_slice_ok():
    assert slice_for_job(["a", "b", "c"], 3, 4) == []


def test_single_job_returns_original():
    assert slice_for_job(KW, 0, 1) == KW
