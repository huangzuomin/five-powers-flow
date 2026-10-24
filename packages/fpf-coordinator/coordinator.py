#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Five-Powers-Flow (FPF) Coordinator CLI Wrapper.

Canonical implementation lives in packages.fpf_coordinator.coordinator.
This wrapper provides backward compatibility for hyphenated CLI execution paths.
"""
from packages.fpf_coordinator.coordinator import *

if __name__ == "__main__":
    import sys
    sys.exit(main())
