<#
  Окончательная вёрстка DOCX средствами Word: длинные таблицы делятся с надписью «Продолжение таблицы N» и повтором головки,
  пересчитываются оглавление и поля, сохраняются DOCX и PDF.
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
$wdActiveEndPageNumber = 3
$MaxSplits = 300
$wdActiveEndPageNumberCaption = 3
$script:Failed = @{}

$continuationText = [regex]::Unescape('\u041f\u0440\u043e\u0434\u043e\u043b\u0436\u0435\u043d\u0438\u0435 \u0442\u0430\u0431\u043b\u0438\u0446\u044b')
$numberPattern = '(?:\u0422\u0430\u0431\u043b\u0438\u0446\u0430|\u0442\u0430\u0431\u043b\u0438\u0446\u044b)\s+([0-9\u0410-\u042f]+(?:\.[0-9]+)?)'

function Get-TableNumber($table) {
    $previous = $table.Range.Paragraphs.Item(1).Previous(1)
    if ($null -ne $previous -and $previous.Range.Text -match $numberPattern) { return $Matches[1] }
    return $null
}

function Get-FirstRowOnNextPage($table) {
    $rows = $table.Rows.Count
    $firstPage = $table.Rows.Item(1).Range.Information($wdActiveEndPageNumber)
    if ($table.Rows.Item($rows).Range.Information($wdActiveEndPageNumber) -eq $firstPage) { return 0 }
    for ($row = 2; $row -le $rows; $row++) {
        if ($table.Rows.Item($row).Range.Information($wdActiveEndPageNumber) -ne $firstPage) { return $row }
    }
    return 0
}

function Keep-CaptionsWithTables($document) {
    foreach ($table in $document.Tables) {
        try {
            $previous = $table.Range.Paragraphs.Item(1).Previous(1)
            if ($null -eq $previous) { continue }
            $text = $previous.Range.Text
            if ($text -notmatch ('^(' + $continuationText + '|' + [regex]::Unescape('Таблица') + ')\s')) { continue }
            $captionPage = $previous.Range.Information($wdActiveEndPageNumberCaption)
            $dataRow = [Math]::Min(2, $table.Rows.Count)
            $tablePage = $table.Rows.Item($dataRow).Range.Information($wdActiveEndPageNumberCaption)
            if ($captionPage -ne $tablePage) { $previous.PageBreakBefore = -1 }
        }
        catch { }
    }
}

function Split-OneTable($document) {
    for ($index = 1; $index -le $document.Tables.Count; $index++) {
        $table = $document.Tables.Item($index)
        $key = $table.Range.Start
        if ($script:Failed.ContainsKey($key) -or $table.Rows.Count -lt 3) { continue }
        try {
            $number = Get-TableNumber $table
            $splitAt = Get-FirstRowOnNextPage $table
            if ($null -eq $number -or $splitAt -lt 3) { continue }
            $headerTexts = @()
            foreach ($cell in $table.Rows.Item(1).Cells) { $headerTexts += $cell.Range.Text.TrimEnd([char]13, [char]7) }
            $table.Split($splitAt)
            $next = $document.Tables.Item($index + 1)
            $gap = $next.Range.Paragraphs.Item(1).Previous(1)
            if ($null -ne $gap) {
                $gap.Range.InsertBefore("$continuationText $number")
                $gap.Alignment = 0
                $gap.FirstLineIndent = 0
                $gap.SpaceBefore = 18
                $gap.KeepWithNext = -1
            }
            $header = $next.Rows.Add($next.Rows.Item(1))
            for ($column = 1; $column -le $header.Cells.Count -and $column -le $headerTexts.Count; $column++) {
                $header.Cells.Item($column).Range.Text = $headerTexts[$column - 1]
            }
            $header.HeadingFormat = -1
            $header.Range.Font.Italic = 0
            $header.Range.ParagraphFormat.KeepWithNext = -1
            return $true
        }
        catch {
            $script:Failed[$key] = $true
        }
    }
    return $false
}

$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
try {
    $document = $word.Documents.Open((Resolve-Path $InputFile).Path, $false, $true)
    $document.Repaginate()
    $splits = 0
    while ($splits -lt $MaxSplits -and (Split-OneTable $document)) {
        $splits++
        $document.Repaginate()
    }
    foreach ($pass in 1..3) {
        $document.Repaginate()
        Keep-CaptionsWithTables $document
    }
    foreach ($contents in $document.TablesOfContents) { $contents.Update() }
    $document.Fields.Update() | Out-Null
    $document.Repaginate()
    foreach ($contents in $document.TablesOfContents) { $contents.UpdatePageNumbers() }
    $document.SaveAs2([ref]$OutputDocx, [ref]$wdFormatXMLDocument)
    $document.ExportAsFixedFormat($OutputPdf, $wdExportFormatPDF)
    Write-Output ([regex]::Unescape('\u0421\u0442\u0440\u0430\u043d\u0438\u0446') + ": " + $document.ComputeStatistics($wdStatisticPages) + "; continuation splits: $splits")
    $document.Close(0)
}
finally {
    $word.Quit()
}
