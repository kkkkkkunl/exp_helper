param(
    [Parameter(Mandatory=$true)][string]$Workbook,
    [Parameter(Mandatory=$true)][string]$OutputDir
)
$ErrorActionPreference = 'Stop'
$qpcrWorkbookPath = (Resolve-Path -LiteralPath $Workbook).Path
if ([IO.Path]::GetExtension($qpcrWorkbookPath) -ne '.xlsx') { throw 'Expected an explicit XLSX file' }
$qpcrEvidencePath = [IO.Path]::GetFullPath($OutputDir)
if (Test-Path -LiteralPath $qpcrEvidencePath) { throw 'Evidence directory already exists; refusing to overwrite' }
[void](New-Item -ItemType Directory -Path $qpcrEvidencePath)
$qpcrExcel = $null
$qpcrBook = $null
$qpcrReport = [ordered]@{engine='Microsoft Excel'; version=$null; workbook=$qpcrWorkbookPath; recalculation='not_run'; mutations=@(); sheets=@(); charts=@()}
try {
    $qpcrExcel = New-Object -ComObject Excel.Application
    $qpcrExcel.Visible = $false
    $qpcrExcel.DisplayAlerts = $false
    $qpcrExcel.ScreenUpdating = $false
    $qpcrExcel.AutomationSecurity = 3
    $qpcrReport.version = $qpcrExcel.Version
    $qpcrBook = $qpcrExcel.Workbooks.Open($qpcrWorkbookPath,0,$false)
    $qpcrExcel.CalculateFullRebuild()
    $qpcrRaw = $qpcrBook.Worksheets.Item('原始数据')
    $qpcrCalc = $qpcrBook.Worksheets.Item('计算过程')
    $qpcrTarget = $null
    for ($qpcrRow=2; $qpcrRow -le $qpcrCalc.UsedRange.Rows.Count; $qpcrRow++) {
        if ($qpcrCalc.Cells.Item($qpcrRow,17).Value2 -eq '可计算' -and $qpcrCalc.Cells.Item($qpcrRow,2).Value2 -ne $qpcrCalc.Cells.Item($qpcrRow,21).Value2) {
            $qpcrTarget = $qpcrRow
            break
        }
    }
    if ($null -eq $qpcrTarget) { throw 'Acceptance mutation checks require a calculable non-calibrator group; no such result exists after recalculation.' }
    if ($null -ne $qpcrTarget) {
        $qpcrScope = [string]$qpcrCalc.Cells.Item($qpcrTarget,1).Value2
        $qpcrGroup = [string]$qpcrCalc.Cells.Item($qpcrTarget,2).Value2
        $qpcrAssay = [string]$qpcrCalc.Cells.Item($qpcrTarget,5).Value2
        $qpcrRefAssay = [string]$qpcrCalc.Cells.Item($qpcrTarget,6).Value2
        $qpcrCalibrator = [string]$qpcrCalc.Cells.Item($qpcrTarget,21).Value2
        foreach ($qpcrMode in @('target_cq','calibrator_reference_cq')) {
            $qpcrEditRow = $null
            for ($qpcrRow=2; $qpcrRow -le $qpcrRaw.UsedRange.Rows.Count; $qpcrRow++) {
                $qpcrMatch = $qpcrRaw.Cells.Item($qpcrRow,4).Value2 -eq $qpcrScope -and $qpcrRaw.Cells.Item($qpcrRow,18).Value2 -eq 1
                if ($qpcrMode -eq 'target_cq') {
                    $qpcrMatch = $qpcrMatch -and $qpcrRaw.Cells.Item($qpcrRow,7).Value2 -eq $qpcrGroup -and $qpcrRaw.Cells.Item($qpcrRow,11).Value2 -eq $qpcrAssay
                } else {
                    $qpcrMatch = $qpcrMatch -and $qpcrRaw.Cells.Item($qpcrRow,7).Value2 -eq $qpcrCalibrator -and $qpcrRaw.Cells.Item($qpcrRow,11).Value2 -eq $qpcrRefAssay
                }
                if ($qpcrMatch) { $qpcrEditRow=$qpcrRow; break }
            }
            if ($null -eq $qpcrEditRow) { throw "No numeric mutation input for $qpcrMode" }
            $qpcrCell = $qpcrRaw.Cells.Item($qpcrEditRow,13)
            $qpcrOriginal = $qpcrCell.Value2
            $qpcrBefore = [double]$qpcrCalc.Cells.Item($qpcrTarget,15).Value2
            try {
                $qpcrCell.Value2 = [double]$qpcrOriginal + 1.0
                $qpcrExcel.CalculateFullRebuild()
                $qpcrAfter = [double]$qpcrCalc.Cells.Item($qpcrTarget,15).Value2
                if ([math]::Abs($qpcrAfter-$qpcrBefore) -lt 1e-10) { throw 'Dependent expression did not update' }
            } finally {
                $qpcrCell.Value2 = $qpcrOriginal
                $qpcrExcel.CalculateFullRebuild()
            }
            $qpcrRestored=[double]$qpcrCalc.Cells.Item($qpcrTarget,15).Value2
            if ([math]::Abs($qpcrRestored-$qpcrBefore) -gt 1e-9) { throw 'Mutation was not restored' }
            $qpcrReport.mutations += [ordered]@{kind=$qpcrMode; input="原始数据!M$qpcrEditRow"; output="计算过程!O$qpcrTarget"; before=$qpcrBefore; after=$qpcrAfter; restored=$qpcrRestored}
        }
    }
    $qpcrExcel.CalculateFullRebuild()
    $qpcrBook.Save()
    $qpcrReport.recalculation='passed'
    $qpcrSheetIndex=0
    foreach ($qpcrSheet in $qpcrBook.Worksheets) {
        $qpcrSheetIndex++
        $qpcrPdf=Join-Path $qpcrEvidencePath ("sheet-{0}.pdf" -f $qpcrSheetIndex)
        $qpcrSheet.ExportAsFixedFormat(0,$qpcrPdf)
        $qpcrReport.sheets += [ordered]@{name=$qpcrSheet.Name; pdf=[IO.Path]::GetFileName($qpcrPdf)}
        $qpcrChartIndex=0
        foreach ($qpcrChart in $qpcrSheet.ChartObjects()) {
            $qpcrChartIndex++
            $qpcrPng=Join-Path $qpcrEvidencePath ("chart-{0}-{1}.png" -f $qpcrSheetIndex,$qpcrChartIndex)
            $qpcrSheet.Activate()
            $qpcrChart.Activate()
            $qpcrChart.Chart.Refresh()
            $qpcrExported = $false
            for ($qpcrExportAttempt=0; $qpcrExportAttempt -lt 3; $qpcrExportAttempt++) {
                [void]$qpcrChart.Chart.Export($qpcrPng,'PNG')
                Start-Sleep -Milliseconds 250
                if ((Test-Path -LiteralPath $qpcrPng) -and (Get-Item -LiteralPath $qpcrPng).Length -gt 100) { $qpcrExported=$true; break }
            }
            if (-not $qpcrExported) { throw 'Native chart PNG export produced no valid image' }
            $qpcrReport.charts += [ordered]@{sheet=$qpcrSheet.Name; file=[IO.Path]::GetFileName($qpcrPng)}
        }
    }
    $qpcrReport | ConvertTo-Json -Depth 8 | Set-Content -Encoding utf8 -LiteralPath (Join-Path $qpcrEvidencePath 'excel-verification.json')
    $qpcrReport | ConvertTo-Json -Depth 8
} finally {
    if ($null -ne $qpcrBook) { $qpcrBook.Close($false); [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($qpcrBook) }
    if ($null -ne $qpcrExcel) { $qpcrExcel.Quit(); [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($qpcrExcel) }
    [GC]::Collect(); [GC]::WaitForPendingFinalizers()
}
