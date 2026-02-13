$requiredIds = @(
    'fileInput',
    'uploadBtn',
    'results-section',
    'history-count',
    'filename-display',
    'audio-player',
    'confidence-display',
    'word-count-display',
    'transcript-container',
    'summary-text',
    'highlights-container',
    'keywords-container',
    'radarChart',
    'play-pause-btn'
)

$htmlPath = "d:\infosys-internship-code\frontend\templates\upload.html"
$htmlContent = Get-Content $htmlPath -Raw

Write-Host "`nVerifying Required IDs..." -ForegroundColor Cyan
Write-Host "=" * 50

$missing = @()
$found = @()

foreach ($id in $requiredIds) {
    if ($htmlContent -match "id=`"$id`"") {
        $found += $id
        Write-Host "[OK] $id" -ForegroundColor Green
    } else {
        $missing += $id
        Write-Host "[MISSING] $id" -ForegroundColor Red
    }
}

Write-Host "`n" ("=" * 50)
Write-Host "Summary:" -ForegroundColor Cyan
Write-Host "Found: $($found.Count) / $($requiredIds.Count)" -ForegroundColor $(if($missing.Count -eq 0){"Green"}else{"Yellow"})
if ($missing.Count -gt 0) {
    Write-Host "`nMissing IDs:" -ForegroundColor Red
    $missing | ForEach-Object { Write-Host "  - $_" -ForegroundColor Red }
} else {
    Write-Host "`nAll required IDs are present!" -ForegroundColor Green
}
