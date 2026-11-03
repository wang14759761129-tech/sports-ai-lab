"""Dedicated fail-closed QA entry, never the production entry."""
import os
os.environ['PTTI_ISOLATED_QA']='1'
from apps.desktop import main
if __name__=='__main__':
 try:
  main()
 except Exception as error:
  import ctypes
  ctypes.windll.user32.MessageBoxW(None,'QA startup refused: '+str(error),'PTTI isolated QA',0x10)
  raise
