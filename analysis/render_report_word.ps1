param(
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot)
)
$docPath = Join-Path $ProjectRoot 'report\中文分析报告.docx'
$qaDir = Join-Path $ProjectRoot 'outputs\qa\report_render'
New-Item -ItemType Directory -Force -Path $qaDir | Out-Null
$pdfPath = Join-Path $qaDir 'report.pdf'
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
try {
    $document = $word.Documents.Open($docPath, $false, $true)
    $document.Repaginate()
    $document.ExportAsFixedFormat($pdfPath, 17)
    $pages = $document.ComputeStatistics(2)
    $document.Close(0)
    Write-Output "Rendered $pages pages to $pdfPath"
} finally {
    try { $word.Quit() } catch { Write-Verbose 'Word process already closed after PDF export.' }
    try { [System.Runtime.InteropServices.Marshal]::ReleaseComObject($word) | Out-Null } catch { Write-Verbose 'COM object already released.' }
}
