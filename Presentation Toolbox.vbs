' Starts the Presentation Toolbox without showing a command line window.
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
base = fso.GetParentFolderName(WScript.ScriptFullName)
shell.CurrentDirectory = base
shell.Run "cmd /c start.bat", 0, False
