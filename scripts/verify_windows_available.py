from pathlib import Path
import unittest,sys
root = Path(__file__).resolve().parents[1]
import os
os.chdir(root)
sys.path.insert(0,str(root))
sys.path.insert(0,str(root/'tests'))
blocked={'test_audio_upload_effects_chain_reverse_pitch_and_loop','test_pitch_frequency_duration_and_legacy_conversion'}
def cases(suite):
    for test in suite:
        if isinstance(test,unittest.TestSuite): yield from cases(test)
        else: yield test
all_tests=list(cases(unittest.defaultTestLoader.discover('tests')))
selected=[test for test in all_tests if test._testMethodName not in blocked]
with Path('windows-supported-tests.log').open('w',encoding='utf-8') as log:
    print('Total discovered:',len(all_tests),file=log)
    print('Deferred due to Windows Application Control blocking SciPy:',', '.join(sorted(blocked)),file=log)
    result=unittest.TextTestRunner(stream=log,verbosity=2).run(unittest.TestSuite(selected))
print('Discovered:',len(all_tests),'Run:',result.testsRun,'Passed:',result.testsRun-len(result.skipped)-len(result.errors)-len(result.failures),'Skipped:',len(result.skipped),'Deferred:',len(all_tests)-len(selected))
raise SystemExit(not result.wasSuccessful())
