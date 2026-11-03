"""Windows resource guards without changing frozen model environments."""
import ctypes
from ctypes import wintypes


class MemoryStatus(ctypes.Structure):
    _fields_ = [('length', wintypes.DWORD), ('load', wintypes.DWORD)] + [
        (name, ctypes.c_ulonglong) for name in ['total_phys', 'available_phys', 'total_page',
        'available_page', 'total_virtual', 'available_virtual', 'available_extended']]


class ProcessMemory(ctypes.Structure):
    _fields_ = [('size', wintypes.DWORD), ('faults', wintypes.DWORD)] + [
        (name, ctypes.c_size_t) for name in ['peak_working', 'working', 'peak_paged',
        'paged', 'peak_nonpaged', 'nonpaged', 'pagefile', 'peak_pagefile']]


def available_ram():
    state = MemoryStatus()
    state.length = ctypes.sizeof(state)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(state)):
        raise OSError('MEMORY_STATUS_UNAVAILABLE')
    return state.available_phys


def process_rss():
    counters = ProcessMemory()
    counters.size = ctypes.sizeof(counters)
    kernel = ctypes.windll.kernel32
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    psapi = ctypes.windll.psapi
    psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]
    if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.size):
        raise OSError('PROCESS_MEMORY_UNAVAILABLE')
    return counters.working
