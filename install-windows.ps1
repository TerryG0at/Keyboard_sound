param(
    [switch]$RemoveStartup
)

$ErrorActionPreference = 'Stop'
$startupFolder = [Environment]::GetFolderPath('Startup')
$startupShortcut = Join-Path $startupFolder 'Keyboard Sound.lnk'

if ($RemoveStartup) {
    if (Test-Path -LiteralPath $startupShortcut) {
        Remove-Item -LiteralPath $startupShortcut
    }
    Write-Output 'Keyboard Sound will no longer start automatically.'
    return
}

$sourceExe = Join-Path $PSScriptRoot 'dist\KeyboardSound.exe'
if (-not (Test-Path -LiteralPath $sourceExe)) {
    throw 'Build dist\KeyboardSound.exe before installing.'
}
$installFolder = Join-Path $env:LOCALAPPDATA 'Programs\KeyboardSound'
$installedExe = Join-Path $installFolder 'KeyboardSound.exe'
New-Item -ItemType Directory -Path $installFolder -Force | Out-Null
Copy-Item -LiteralPath $sourceExe -Destination $installedExe -Force

$shortcutShell = New-Object -ComObject WScript.Shell
$desktopFolder = [Environment]::GetFolderPath('Desktop')
$desktopShortcut = Join-Path $desktopFolder 'Keyboard Sound.lnk'
foreach ($shortcutPath in @($desktopShortcut, $startupShortcut)) {
    $shortcut = $shortcutShell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = $installedExe
    $shortcut.WorkingDirectory = $installFolder
    $shortcut.IconLocation = "$installedExe,0"
    $shortcut.Description = 'Keyboard Sound'
    if ($shortcutPath -eq $startupShortcut) {
        $shortcut.Arguments = '--tray'
    }
    $shortcut.Save()
}
Write-Output "Installed: $installedExe"
Write-Output "Desktop shortcut: $desktopShortcut"
Write-Output "Windows startup shortcut: $startupShortcut"
