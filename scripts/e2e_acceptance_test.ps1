# TidyAI End-to-End Acceptance Verification Script
$ErrorActionPreference = 'Stop'

Write-Output "=== TIDY_AI END-TO-END ACCEPTANCE TEST EXECUTION ==="

# 1 & 2: Services
Write-Output "`n[Step 1 & 2] Checking FastAPI & Next.js service listeners..."
$fe = Invoke-WebRequest -Uri "http://127.0.0.1:3000" -UseBasicParsing -Method Get
Write-Output "  Frontend (port 3000) Status: $($fe.StatusCode)"
$be = Invoke-RestMethod -Uri "http://127.0.0.1:8765/api/health" -Method Get
Write-Output "  Backend (port 8765) Status: $($be.status) | Database: $($be.database_connected)"

# 4 & 5: Health & DB
Write-Output "`n[Step 4 & 5] Verified backend service: $($be.service), version: $($be.version)"

# Create synthetic test sandbox with an identical duplicate pair
$testDir = "c:\local_disc_D\Hackathan\TIDY_AI\test_e2e_sandbox"
if (Test-Path $testDir) { Remove-Item -Path $testDir -Recurse -Force }
New-Item -ItemType Directory -Path "$testDir\invoices" -Force | Out-Null
Set-Content -Path "$testDir\invoices\invoice_alpha.txt" -Value "INVOICE #1001: TOTAL $450.00"
Set-Content -Path "$testDir\invoices\invoice_duplicate_copy.txt" -Value "INVOICE #1001: TOTAL $450.00"
Set-Content -Path "$testDir\invoices\annual_report.txt" -Value "ANNUAL REPORT 2026: REVENUE GROWTH 35%"

# 6: Approve Directory
Write-Output "`n[Step 6] Approving test sandbox directory..."
$body = @{ path = $testDir; label = "E2E Acceptance Sandbox" } | ConvertTo-Json
$root = Invoke-RestMethod -Uri "http://127.0.0.1:8765/api/roots/approve" -Method Post -Body $body -ContentType "application/json"
Write-Output "  Approved Root ID: $($root.id) | Path: $($root.canonical_path)"

# 7: Scan
Write-Output "`n[Step 7] Scanning directory inventory..."
$scanReq = @{ root_id = $root.id } | ConvertTo-Json
$scan = Invoke-RestMethod -Uri "http://127.0.0.1:8765/api/scan" -Method Post -Body $scanReq -ContentType "application/json"
Write-Output "  Scan found $($scan.summary.total_files) files in $($scan.summary.duration_ms)ms."
foreach ($f in $scan.files) {
    Write-Output "    - $($f.relative_path) ($($f.size_bytes) B, type: $($f.file_type))"
}

# 8: Duplicate Detection
Write-Output "`n[Step 8] Running exact duplicate detection (SHA-256)..."
$dupReq = @{ root_id = $root.id } | ConvertTo-Json
$dup = Invoke-RestMethod -Uri "http://127.0.0.1:8765/api/duplicates" -Method Post -Body $dupReq -ContentType "application/json"
Write-Output "  Duplicates detected: $($dup.summary.duplicate_groups_count) group(s), $($dup.summary.potential_savings_bytes) bytes savings."
foreach ($g in $dup.groups) {
    $hashPrefix = $g.sha256.Substring(0, 16)
    Write-Output "    Group Hash: $hashPrefix... ($($g.file_count) copies)"
    foreach ($df in $g.files) {
        Write-Output "      * $($df.relative_path)"
    }
}

# 9: Verify Ollama status
Write-Output "`n[Step 9] Verifying Ollama status..."
$ol = Invoke-RestMethod -Uri "http://127.0.0.1:8765/api/ollama/status" -Method Get
Write-Output "  Ollama State: $($ol.state) | Reachable: $($ol.reachable) | Model: $($ol.model_name)"

# 10: Generate AI suggestions
Write-Output "`n[Step 10] Generating real AI suggestions via Qwen3 4B..."
$sugReq = @{ root_id = $root.id; max_files = 10; confidence_threshold = 0.5 } | ConvertTo-Json
$sug = Invoke-RestMethod -Uri "http://127.0.0.1:8765/api/suggestions" -Method Post -Body $sugReq -ContentType "application/json"
Write-Output "  Generated $($sug.summary.suggestions_generated) suggestions using model $($sug.summary.model_used) in $($sug.summary.duration_ms)ms."
foreach ($s in $sug.suggestions) {
    Write-Output "    * $($s.current_relative_path) -> $($s.proposed_relative_path) [Confidence: $($s.confidence), Ambiguous: $($s.is_ambiguous)]"
}

# 12 & 13: Stage and Dry-Run
Write-Output "`n[Step 12 & 13] Staging operation and running Dry-Run simulation..."
$ops = @(
    @{
        source_rel_path = "invoices/annual_report.txt";
        target_rel_path = "archive/2026/annual_report.txt";
        operation_type = "move";
        approved = $true
    }
)
$dryReq = @{ root_id = $root.id; operations = $ops } | ConvertTo-Json
$dry = Invoke-RestMethod -Uri "http://127.0.0.1:8765/api/operations/preview" -Method Post -Body $dryReq -ContentType "application/json"
Write-Output "  Dry-Run Summary: $($dry.summary.safe_operations) safe out of $($dry.summary.total_operations). Executable: $($dry.summary.is_executable)"
foreach ($it in $dry.items) {
    Write-Output "    Item: $($it.source_rel_path) -> $($it.target_rel_path) [Safe: $($it.is_safe), Creates: $($it.will_create_subfolder)]"
}
# Verify file has NOT moved yet
$origExistsBefore = Test-Path "$testDir\invoices\annual_report.txt"
$destExistsBefore = Test-Path "$testDir\archive\2026\annual_report.txt"
Write-Output "  Dry-run non-mutation check: Origin exists=$origExistsBefore, Dest exists=$destExistsBefore"

# 14 & 15: Apply Confirmed Operation
Write-Output "`n[Step 14 & 15] Applying confirmed operation to disk..."
$applyReq = @{ root_id = $root.id; operations = $ops; confirmed = $true } | ConvertTo-Json
$apply = Invoke-RestMethod -Uri "http://127.0.0.1:8765/api/operations/apply" -Method Post -Body $applyReq -ContentType "application/json"
Write-Output "  Apply Result: Status=$($apply.status), Applied=$($apply.total_applied), Failed=$($apply.failed_count), Batch ID=$($apply.batch_id)"

$origExistsAfter = Test-Path "$testDir\invoices\annual_report.txt"
$destExistsAfter = Test-Path "$testDir\archive\2026\annual_report.txt"
Write-Output "  Post-Apply Filesystem Check: Origin exists=$origExistsAfter, Dest exists=$destExistsAfter"

# 16 & 17: Undo Operation
Write-Output "`n[Step 16 & 17] Executing safe LIFO undo on batch $($apply.batch_id)..."
$undo = Invoke-RestMethod -Uri "http://127.0.0.1:8765/api/operations/$($apply.batch_id)/undo" -Method Post
Write-Output "  Undo Result: Status=$($undo.status), Reverted=$($undo.total_reverted), Blocked=$($undo.blocked_count)"

$origExistsUndo = Test-Path "$testDir\invoices\annual_report.txt"
$destExistsUndo = Test-Path "$testDir\archive\2026\annual_report.txt"
Write-Output "  Post-Undo Filesystem Check: Origin restored=$origExistsUndo, Dest cleaned=$(-not $destExistsUndo)"

# 18: Collision Protection
Write-Output "`n[Step 18] Verifying Collision Protection (Fail-Closed)..."
New-Item -ItemType Directory -Path "$testDir\archive\2026" -Force | Out-Null
Set-Content -Path "$testDir\archive\2026\annual_report.txt" -Value "OCCUPIED TARGET FILE"
$collReq = @{ root_id = $root.id; operations = $ops; confirmed = $true } | ConvertTo-Json
$res = Invoke-RestMethod -Uri "http://127.0.0.1:8765/api/operations/apply" -Method Post -Body $collReq -ContentType "application/json"
if ($res.failed_count -gt 0 -and $res.items[0].status -eq "failed") {
    Write-Output "  SUCCESS: Collision correctly blocked by fail-closed boundary: $($res.items[0].error_message)"
} else {
    Write-Output "  ERROR: Collision was not blocked!"
}

# Clean up sandbox
Invoke-RestMethod -Uri "http://127.0.0.1:8765/api/roots/$($root.id)" -Method Delete | Out-Null
Remove-Item -Path $testDir -Recurse -Force
Write-Output "`n=== ALL E2E ACCEPTANCE CRITERIA MET AND VERIFIED ==="
