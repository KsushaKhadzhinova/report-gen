# Обновляет оглавление и поля, сохраняет DOCX и PDF. Запуск: powershell -NoProfile -ExecutionPolicy Bypass -File scriptsefresh_word.ps1 <файл.docx> <файл.pdf>
param([Parameter(Mandatory=$true)][string]$Docx, [Parameter(Mandatory=$true)][string]$Pdf)
$ErrorActionPreference = "Stop"
$full = (Resolve-Path $Docx).Path
$Pdf = [System.IO.Path]::GetFullPath($Pdf)
$tmp = [System.IO.Path]::Combine([System.IO.Path]::GetDirectoryName($full), "refresh_tmp.docx")
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
try {
    $document = $word.Documents.Open($full)
    $document.Repaginate()
    foreach ($contents in $document.TablesOfContents) { $contents.Update() }
    $document.Fields.Update() | Out-Null
    $document.Repaginate()
    foreach ($contents in $document.TablesOfContents) { $contents.UpdatePageNumbers() }
    $document.SaveAs2([ref]$tmp, [ref]12)
    $document.ExportAsFixedFormat($Pdf, 17)
    Write-Output ("Страниц: " + $document.ComputeStatistics(2))
    $document.Close(0)
}
finally { $word.Quit() }
Move-Item -Force $tmp $full
