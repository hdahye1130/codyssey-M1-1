"""Rebuild in a clean temporary folder; compare all generated files byte for byte."""
from pathlib import Path
import tempfile
import shutil
import subprocess
import sys
import json
import hashlib

root = Path(__file__).resolve().parent
with tempfile.TemporaryDirectory(prefix='solar_reproduce_') as tmp:
    target = Path(tmp)
    for name in ['analysis.py','README.md','requirements.txt']:
        shutil.copy2(root/name,target/name)
    (target/'data').mkdir()
    shutil.copy2(root/'data/kpx_original.csv',target/'data/kpx_original.csv')
    completed = subprocess.run([sys.executable,str(target/'analysis.py')],cwd=tmp,capture_output=True,text=True,check=True)
    names = ['REPORT.md'] + [str(p.relative_to(root)) for p in sorted((root/'images').glob('*.png'))] + [str(p.relative_to(root)) for p in sorted((root/'data').glob('*')) if p.name not in ['kpx_original.csv','reproducibility.json']]
    checks = {}
    for name in names:
        checks[name] = (root/name).read_bytes() == (target/name).read_bytes()
    assert all(checks.values()), checks
    result = {'clean_output_rebuild_passed':True,'files_identical':checks,
              'python_version':sys.version.split()[0],
              'input_sha256':hashlib.sha256((root/'data/kpx_original.csv').read_bytes()).hexdigest(),
              'environment_note':'Separate empty output directory using current Python and installed dependencies; not a new operating system.'}
    (root/'data/reproducibility.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))