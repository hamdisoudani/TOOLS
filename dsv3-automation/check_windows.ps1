Add-Type @"
using System;
using System.Runtime.InteropServices;
using System.Text;
public class W {
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumWindowsProc lpEnumFunc, IntPtr lParam);
  public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);
  [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr hWnd, StringBuilder lpString, int nMaxCount);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint lpdwProcessId);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);
  public struct RECT { public int Left; public int Top; public int Right; public int Bottom; }
}
"@
$callback = [W+EnumWindowsProc] {
  param($hWnd, $lParam)
  $title = New-Object System.Text.StringBuilder(256)
  [void][W]::GetWindowText($hWnd, $title, 256)
  $pid = 0
  [void][W]::GetWindowThreadProcessId($hWnd, [ref]$pid)
  $rect = New-Object W+RECT
  [void][W]::GetWindowRect($hWnd, [ref]$rect)
  if ($title.Length -gt 0 -and $pid -ne 0) {
    Write-Host "PID=$pid HWND=$hWnd Title='$($title.ToString())' Visible=$([W]::IsWindowVisible($hWnd)) Pos=($($rect.Left),$($rect.Top)) Size=($($rect.Right-$rect.Left)x$($rect.Bottom-$rect.Top))"
  }
  return $true
}
[void][W]::EnumWindows($callback, [IntPtr]::Zero)
