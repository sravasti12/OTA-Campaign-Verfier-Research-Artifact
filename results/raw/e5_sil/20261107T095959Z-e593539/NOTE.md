# Incomplete run: do not cite

This SIL sweep, from clean commit `e593539`, stopped after 1,747 of 6,360 runs with exit code 4. It wrote no manifest.

The Git Bash shell that started it reported `fork: ... exit code 0xC000026B`. That Windows status means a process could not start because the window station was shutting down, as happens when the machine sleeps or the user logs off. The Python process died with the shell. The first incomplete run, `20261106T170913Z-239d040`, stopped the same way at a similar point.

The complete run, `20261108T074756Z-e593539`, used the same commit. It ran as a separate Windows process that asked the system not to sleep.

This note was added afterwards, by hand. Every other file in this folder is as the run left it.
