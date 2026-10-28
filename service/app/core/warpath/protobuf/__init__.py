"""Generated Warpath protobuf modules (untouched — DO NOT EDIT any *_pb2.py
file in this directory; regenerate from the .proto sources instead).

These files were generated with plain top-level imports (e.g.
``import common_pb2 as common__pb2`` inside down_pb2.py) rather than
package-relative ones, because they were originally generated to sit flat
next to each other with no package at all. Rewriting those imports to be
package-relative risks the protobuf runtime registering the same .proto
twice under two different module identities (once here, once wherever else
a flat ``import common_pb2`` resolves), which raises a descriptor-pool
collision at import time.

Instead, this __init__ puts this directory on sys.path (once) before any of
the generated modules are imported, so their internal flat imports resolve
exactly as they did in the original single-directory layout — the generated
files themselves stay byte-for-byte untouched.
"""

import os
import sys

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)
