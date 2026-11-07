"""Resident-memory observations including native allocations; never tracemalloc totals."""
from __future__ import annotations

import os
import sys
from typing import Any


def system_memory() -> dict[str, Any]:
    """Record physical host RAM and available RAM where the platform exposes them."""
    if os.name == 'nt':
        import ctypes
        from ctypes import wintypes
        class Status(ctypes.Structure):
            _fields_ = [('length', wintypes.DWORD), ('load', wintypes.DWORD)] + [
                (name, ctypes.c_ulonglong) for name in ('total', 'available', 'page_total', 'page_available',
                                                       'virtual_total', 'virtual_available', 'extended')]
        status = Status()
        status.length = ctypes.sizeof(status)
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.GlobalMemoryStatusEx.argtypes = [ctypes.POINTER(Status)]
        kernel.GlobalMemoryStatusEx.restype = wintypes.BOOL
        if kernel.GlobalMemoryStatusEx(ctypes.byref(status)):
            return {'physical_total_bytes': status.total, 'physical_available_bytes': status.available, 'error': None}
        return {'physical_total_bytes': None, 'physical_available_bytes': None,
                'error': f'GlobalMemoryStatusEx {ctypes.get_last_error()}'}
    try:
        return {'physical_total_bytes': os.sysconf('SC_PHYS_PAGES')*os.sysconf('SC_PAGE_SIZE'),
                'physical_available_bytes': os.sysconf('SC_AVPHYS_PAGES')*os.sysconf('SC_PAGE_SIZE'), 'error': None}
    except (ValueError, OSError, AttributeError) as error:
        return {'physical_total_bytes': None, 'physical_available_bytes': None, 'error': type(error).__name__}


def memory_observation(pid: int | None = None) -> dict[str, Any]:
    """Return OS peak resident/working-set bytes or an explicit unavailable reason."""
    if os.name == 'nt':
        import ctypes
        from ctypes import wintypes

        class Counters(ctypes.Structure):
            _fields_ = [('cb', wintypes.DWORD), ('faults', wintypes.DWORD)] + [
                (name, ctypes.c_size_t) for name in ('peak', 'working', 'quota_peak_paged', 'quota_paged',
                    'quota_peak_nonpaged', 'quota_nonpaged', 'pagefile', 'peak_pagefile')]

        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        psapi = ctypes.WinDLL('psapi', use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
        psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
        handle = kernel.OpenProcess(0x0400 | 0x0010, False, pid or os.getpid())
        if not handle:
            return {'peak_bytes': None, 'method': 'windows_peak_working_set', 'error': f'OpenProcess error {ctypes.get_last_error()}'}
        try:
            counters = Counters()
            counters.cb = ctypes.sizeof(counters)
            if not psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
                return {'peak_bytes': None, 'method': 'windows_peak_working_set', 'error': f'GetProcessMemoryInfo error {ctypes.get_last_error()}'}
            return {'peak_bytes': counters.peak, 'working_bytes': counters.working,
                    'method': 'windows_peak_working_set', 'error': None}
        finally:
            kernel.CloseHandle(handle)
    if pid is None or pid == os.getpid():
        import resource
        factor = 1 if sys.platform == 'darwin' else 1024
        return {'peak_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * factor,
                'method': 'unix_self_ru_maxrss', 'error': None}
    try:
        from pathlib import Path
        values = dict(line.split(':', 1) for line in Path(f'/proc/{pid}/status').read_text().splitlines() if ':' in line)
        return {'peak_bytes': int(values['VmHWM'].split()[0]) * 1024,
                'method': 'linux_sampled_VmHWM', 'error': None}
    except (OSError, KeyError, ValueError) as error:
        return {'peak_bytes': None, 'method': 'unavailable', 'error': type(error).__name__}
