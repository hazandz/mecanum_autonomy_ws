import subprocess,sys,time
for _ in range(40):
 p=subprocess.run(['xdpyinfo'],capture_output=True,timeout=1)
 if p.returncode==0:sys.exit(0)
 time.sleep(.1)
sys.exit(1)
