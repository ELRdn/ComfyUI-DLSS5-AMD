"""TEST DOUBLE ONLY. No DLSS, GPU, or neural inference occurs in this program."""
import argparse
import json
import os
from pathlib import Path
import sys
import time

parser=argparse.ArgumentParser()
for name in ('input','output','width','height','frames','out','seconds','worker-seconds'):
    parser.add_argument('--'+name, required=True)
parser.add_argument('--proxy',action='store_true')
parser.add_argument('--fast-isolated',action='store_true')
a=parser.parse_args()
mode=os.environ.get('AMD_NR_TEST_MODE','ok')
print('TEST DOUBLE ONLY: no neural inference',flush=True)
if mode=='sleep': time.sleep(20)
if mode=='exit': sys.exit(7)
raw=bytearray(Path(a.input).read_bytes())
# Reversible per-pixel change, keeping the order. Deliberately NOT an enhancer.
for i in range(0,len(raw),4): raw[i] ^= 1
Path(a.output).write_bytes(raw[:-4] if mode=='truncated' else raw)
frames=int(a.frames)
report={'input_frames':frames,'output_frames':frames,'neural_frames_completed':frames,
        'completed':True,'status':'ok','error':'','neural_jobs_logged':2*frames,'enabled':True,
        'TEST_DOUBLE_NOT_REAL_INFERENCE':True}
if mode=='missing': sys.exit(0)
if mode=='wrong_count': report['output_frames']=frames-1
if mode=='false_completed': report['completed']=False
if mode=='fake_bool_count': report['input_frames']=True
if mode=='disabled': report['enabled']=False
if mode=='no_jobs': report['neural_jobs_logged']=0
if mode=='no_neural': report['neural_frames_completed']=0
if mode=='error': report['error']='runtime failure'
if mode=='bad_status': report['status']='unknown'
if mode=='partial': Path(a.output+'.partial').write_bytes(b'partial')
path=Path(a.out)/'engine-report.json'
path.write_text('{' if mode=='bad_json' else json.dumps(report))
(Path(a.out)/'child-env.json').write_text(json.dumps({'hip':os.environ.get('HIP_VISIBLE_DEVICES')}))
