Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public class W {
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int n);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool MoveWindow(IntPtr h, int x, int y, int w, int ht, bool r);
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr h, System.Text.StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumWindowsProc proc, IntPtr p);
  public delegate bool EnumWindowsProc(IntPtr h, IntPtr p);
}
'@
$procs = Get-Process -Name 'Dork*' -ErrorAction SilentlyContinue
foreach ($p in $procs) {
  Write-Host "PID=$($p.Id) HWND=$($p.MainWindowHandle)"
  $h = $p.MainWindowHandle
  if ($h -ne 0) {
    [W]::ShowWindow($h, 9)  # SW_RESTORE
    [W]::ShowWindow($h, 3)  # SW_MAXIMIZE
    [W]::MoveWindow($h, 0, 0, 1280, 720, $true)
    [W]::SetForegroundWindow($h)
    Write-Host "Maximized."
  }
}
