"""Package the delivered qPCR skills and template; never install or run Git."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[2]

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def files(directory):
    for p in sorted(directory.rglob('*')):
        if p.is_symlink():raise ValueError('Package cannot contain symbolic links')
        if p.is_file() and not any(x.startswith('.') or x=='__pycache__' for x in p.relative_to(directory).parts) and p.suffix not in ('.pyc','.pyo'):
            yield p

def package(out,verification):
    verification=Path(verification).resolve()
    proof=json.loads(verification.read_text(encoding='utf-8'))
    if proof.get('status')!='passed':raise ValueError('Release requires actual passed verification evidence')
    for filename,digest in proof['source_files'].items():
        path=(ROOT/filename).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file() or sha(path)!=digest:
            raise ValueError('Verified source changed: '+filename)
    out=Path(out).resolve()
    if any(out.is_relative_to(ROOT/name) for name in ('cell-qpcr','qpcr-ddcq')):raise ValueError('Output must be outside skill source')
    out.mkdir(parents=True,exist_ok=True)
    names=['cell-qpcr-1.0.0.zip','qpcr-ddcq-1.0.0.zip','qpcr-skills-and-template-1.0.0.zip','qpcr-release-manifest.json',verification.name]
    if any((out/n).exists() for n in names):raise FileExistsError('Release output already exists; refusing overwrite')
    contents=[]
    planned=[p for name in ('cell-qpcr','qpcr-ddcq') for p in files(ROOT/name)]
    planned.extend([ROOT/'experiment-workflow/assets/qPCR.md',ROOT/'experiment-workflow/assets/legacy/qPCR-1.0.0.md'])
    if any(p.relative_to(ROOT).as_posix() not in proof['source_files'] for p in planned):
        raise ValueError('Unverified source was added after the verification record')
    for name in ('cell-qpcr','qpcr-ddcq'):
        paths=list(files(ROOT/name))
        with zipfile.ZipFile(out/(name+'-1.0.0.zip'),'w',zipfile.ZIP_DEFLATED) as z:
            for path in paths:z.write(path,path.relative_to(ROOT).as_posix())
        contents.extend(paths)
    contents.extend([ROOT/'experiment-workflow/assets/qPCR.md',ROOT/'experiment-workflow/assets/legacy/qPCR-1.0.0.md'])
    docs=ROOT/'docs/qpcr-实施说明与验证.md'
    if docs.is_file():contents.append(docs)
    if verification.is_relative_to(ROOT):contents.append(verification)
    with zipfile.ZipFile(out/'qpcr-skills-and-template-1.0.0.zip','w',zipfile.ZIP_DEFLATED) as z:
        for path in contents:z.write(path,path.relative_to(ROOT).as_posix())
    result={'release':'1.0.0','template_version':'2.0.0','template_name':'cell-qpcr',
            'requires':['Python 3.9+','workflow experiment-skill version 1 numeric contract','workflow Markdown embedded staged templates','openpyxl and XlsxWriter for file analysis'],
            'installation':'Merge project configuration; install each skill using existing skill_store; no automatic install, Git or archive.',
            'files':{p.relative_to(ROOT).as_posix():sha(p) for p in contents},
            'packages':{name:sha(out/name) for name in names if name.endswith('.zip')},
            'verification':{'evidence_file':verification.name,'evidence_sha256':sha(verification),'summary':proof['summary']},
            'limits':['Synthetic acceptance is not a biological conclusion or real experiment QC certificate','Other engines and instrument-specific conditions require actual validation','Generic creator validator does not model project-specific frontmatter; actual project installer/parser and references are validated.']}
    (out/'qpcr-release-manifest.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    (out/verification.name).write_bytes(verification.read_bytes())
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);p.add_argument('--verification',required=True);a=p.parse_args()
    result=package(a.output,a.verification)
    print(json.dumps({'status':'packaged','output':str(Path(a.output).resolve()),'packages':result['packages']},ensure_ascii=False))
