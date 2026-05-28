import os, sys

# ローカル実行時に routers / services / repositories 等を直接 import できるようにする
_src_dir = os.path.dirname(__file__)
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)
