from src.memory.episodic_memory import EpisodicMemory
import tempfile
import shutil


def test_store_and_query_episode(tmp_path):
    storage = tmp_path / 'episodes'
    mem = EpisodicMemory(storage_dir=str(storage))

    ep1 = {
        'trigger': 'error',
        'query': 'ValueError when parsing',
        'action': 'fixed parser by adding strip()',
        'result': 'success',
        'resolution': 'strip input before parse',
    }
    eid = mem.store_episode(ep1)
    assert isinstance(eid, str)

    res = mem.query_episodes('ValueError')
    assert len(res) >= 1
    assert res[0]['resolution'] == 'strip input before parse'
