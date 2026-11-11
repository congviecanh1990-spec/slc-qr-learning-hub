from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import subprocess,sys
root=Path(__file__).resolve().parent
scripts=sorted((root/'tests').glob('test_*.py'))
def run(t):
 try:
  p=subprocess.run([sys.executable,str(t)],cwd=root,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=50)
  return t.name,p.returncode,(p.stdout+p.stderr)[-1000:]
 except subprocess.TimeoutExpired:return t.name,124,'TIMEOUT'
with ThreadPoolExecutor(max_workers=8) as ex:
 results=[f.result() for f in as_completed([ex.submit(run,t) for t in scripts])]
for name,code,msg in sorted(results):
 if code: print('FAIL',name,'\n',msg)
print('RESULT',sum(code==0 for _,code,_ in results),'/',len(scripts),'passed')
if any(code for _,code,_ in results): sys.exit(1)
