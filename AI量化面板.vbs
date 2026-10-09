' AI Quant Panel one-click launcher.
' Simulation only, local matching, NO real broker account.
' Double-click: silently starts the backend (if needed) and opens the panel
' in the default browser at http://localhost:8000/ . No console window.
Option Explicit
Dim ws, fso, projDir, pyw, cmd
Set ws = CreateObject("Wscript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
projDir = fso.GetParentFolderName(WScript.ScriptFullName)
pyw = projDir & "\venv\Scripts\pythonw.exe"
If Not fso.FileExists(pyw) Then pyw = "pythonw.exe"
cmd = """" & pyw & """ """ & projDir & "\scripts\launch_panel.py"" --open"
ws.Run cmd, 0, False
