' ============================================================
' Quant panel guard / quant:// protocol handler (ASCII only)
' Used two ways:
'   1) Scheduled task QuantPanelGuard runs this every 5 minutes.
'   2) The in-page "Start backend" button opens quant://start-backend,
'      which the OS routes to this script.
' It checks TCP port 8000; if nothing listens, it starts the Flask
' panel silently. It is idempotent: running it repeatedly is harmless.
' ============================================================
Option Explicit

Dim sh, fso, rootDir, batPath
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
' This file lives in <root>\scripts ; its parent's parent is the project root.
rootDir = fso.GetParentFolderName(fso.GetParentFolderName(WScript.ScriptFullName))
batPath = rootDir & "\scripts\start_panel_quiet.bat"

If Not PortListening() Then
    ' 0 = hidden window, False = do not wait
    sh.Run """" & batPath & """", 0, False
End If

Function PortListening()
    Dim exec, out
    PortListening = False
    Set exec = sh.Exec("cmd /c netstat -ano -p tcp | findstr "":8000"" | findstr LISTENING")
    out = ""
    Do While Not exec.StdOut.AtEndOfStream
        out = out & exec.StdOut.ReadLine()
    Loop
    If InStr(out, ":8000") > 0 Then PortListening = True
End Function
