<#
  Окончательная вёрстка DOCX средствами Word: пересчёт оглавления и полей, сохранение DOCX и экспорт в PDF.
  Запуск: powershell -NoProfile -ExecutionPolicy Bypass -File scripts\word_finalize.ps1 <вход.docx> <выход.docx> <выход.pdf>
  Нужен установленный Microsoft Word. Исходный файл не изменяется.
#>
param(
    [Parameter(Mandatory = $true)][string]$InputFile,
    [Parameter(Mandatory = $true)][string]$OutputDocx,
    [Parameter(Mandatory = $true)][string]$OutputPdf
)

$ErrorActionPreference = "Stop"
$wdFormatXMLDocument = 12
$wdExportFormatPDF = 17
$wdStatisticPages = 2

$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
try {
    $document = $word.Documents.Open((Resolve-Path $InputFile).Path, $false, $true)
    $document.Repaginate()
    foreach ($contents in $document.TablesOfContents) { $contents.Update() }
    $document.Fields.Update() | Out-Null
    $document.Repaginate()
    foreach ($contents in $document.TablesOfContents) { $contents.UpdatePageNumbers() }
    $document.SaveAs2([ref]$OutputDocx, [ref]$wdFormatXMLDocument)
    $document.ExportAsFixedFormat($OutputPdf, $wdExportFormatPDF)
    Write-Output ("Страниц: " + $document.ComputeStatistics($wdStatisticPages))
    $document.Close(0)
}
finally {
    $word.Quit()
}
