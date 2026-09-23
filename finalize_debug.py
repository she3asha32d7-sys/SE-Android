from pathlib import Path
import traceback
try:
    exec(Path('..','finalize_v7.py').read_text(), {'__name__':'__main__'})
    Path('finalizer_trace.txt').write_text('FINALIZER_OK')
except Exception:
    Path('finalizer_trace.txt').write_text(traceback.format_exc())
print(Path('finalizer_trace.txt').read_text())
