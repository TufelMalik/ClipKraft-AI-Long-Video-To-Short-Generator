from speaker_identity import IdentityRegistry


def test_anonymous_identity_survives_a_new_camera_observation():
    registry = IdentityRegistry()
    a = registry.assign([1,0,0])
    b = registry.assign([0,1,0])
    assert registry.assign([.98,.02,0])==a
    assert registry.assign([.02,.98,0])==b


def test_two_visible_faces_cannot_take_the_same_id():
    registry = IdentityRegistry()
    first = registry.assign([1,0])
    assert registry.assign([1,0],exclude=[first])!=first


def test_uncertain_or_missing_embedding_is_not_a_false_match():
    registry = IdentityRegistry(threshold=.8)
    a = registry.assign([1,0])
    assert registry.assign([0,1])!=a
    assert registry.assign(None)!=a
    assert registry.assign([0,0])!=a
