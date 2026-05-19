#!/usr/bin/env python3
# Entry point for PyInstaller — freeze_support and start method must be set first
import multiprocessing
multiprocessing.freeze_support()

# 'spawn' is required for PyInstaller compatibility; 'forkserver' breaks frozen binaries
if __name__ == '__main__':
    multiprocessing.set_start_method('spawn')
    from gogdl.cli import main
    main()
