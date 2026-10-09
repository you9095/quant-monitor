' ============================================================
' Quant panel guard (ASCII only) - legacy/fallback entry.
' The quant:// protocol and the QuantPanelGuard scheduled task
' are registered to run: pythonw.exe scripts\launch_panel.py
' directly (no console flash). This VBS is kept as a backup and
' does the same thing: run launch_panel.py hidden and idempotent.
' Simulation only, local matching, NO real broker account.
' ============================================================
Option Explicit

Dim sh, fso, scriptsDir, rootDir, pyw, launcher
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

scriptsDir = fso.GetParentFolderName(WScript.ScriptFullName)
rootDir = fso.GetParentFolderName(scriptsDir)
pyw = rootDir & "\venv\Scripts\pythonw.exe"
If Not fso.FileExists(pyw) Then pyw = "pythonw.exe"
launcher = scriptsDir & "\launch_panel.py"

' 0 = hidden window, False = do not wait for it to finish
sh.Run """" & pyw & """ """ & launcher & """", 0, False
