import pytest

from channel_safety import Ledger, SafetyError, select_channel, same_clip, validate_profiles


def profiles():
    return {'channels':[{'id':'finance','niche':'finance','creators':[
        {'id':'creator-a'}]}]}


def sig(label='a', audio=None):
    return {'sha256':label,'duration':30.,'visual':['100']*12,'audio':audio or [100,0]*32}


def test_channel_without_creators_can_process():
    data = {'channels':[{'id':'finance','niche':'finance','creators':[]}]}
    assert select_channel(data,'finance','finance') is data['channels'][0]
    assert select_channel(data,'finance',None) is data['channels'][0]


def test_niche_mismatch_is_still_blocked_and_legacy_permissions_are_ignored():
    with pytest.raises(SafetyError,match='niche'):
        select_channel(profiles(),'finance','tech')
    data = profiles()
    data['channels'][0]['creators'][0]['expires'] = '2026-01-01'
    assert select_channel(data,'finance','finance') is data['channels'][0]


def test_creator_profiles_need_no_permission_reference():
    data = {'channels':[{'id':'x','niche':'tech','creators':[{'id':'a'}]}]}
    assert validate_profiles(data) == data


def test_unknown_channel_is_still_rejected():
    with pytest.raises(SafetyError,match='Unknown channel'):
        select_channel(profiles(),'missing','finance')


def test_source_tracking_handles_an_omitted_creator(tmp_path):
    ledger = Ledger(str(tmp_path/'ledger.sqlite'))
    assert ledger.claim('job:0','finance',None,sig(),now=100)['weekly_clips'] == 1


def test_same_picture_with_different_audio_is_not_a_duplicate():
    assert not same_clip(sig(),sig('b',[0,100]*32))
    assert same_clip(sig(),sig('reencoded'))


def test_cross_channel_duplicates_and_same_channel_duplicates_are_blocked(tmp_path):
    ledger = Ledger(str(tmp_path/'ledger.sqlite'))
    warning = ledger.claim('job:0','finance','creator-a',sig(),now=100)
    assert warning['warning']
    for channel in ['tech','finance']:
        with pytest.raises(SafetyError,match='Duplicate'):
            ledger.claim('other:0',channel,'creator-a',sig(),now=101)
    assert ledger.claim('job:0','finance','creator-a',sig(),now=102)['weekly_clips']==1
