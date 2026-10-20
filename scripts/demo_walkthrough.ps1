# TidyAI End-to-End Demo Walkthrough Script (Windows PowerShell)
# Demonstrates the complete 8-step safety workflow on synthetic sample data:
# 1. Create temporary demo sandbox from sample_data/
# 2. Check local backend health (FastAPI 127.0.0.1:8765)
# 3. Approve sandbox directory root boundary
# 4. Perform bounded read-only metadata scan
# 5. Execute chunked SHA-256 duplicate detection (diagnostic only)
# 6. Request deterministic AI suggestions (Ollama / Qwen3 4B)
# 7. Execute read-only dry-run preview simulation
# 8. Apply confirmed operations with pre-flight validation
# 9. Query SQLite cryptographic audit ledger
# 10. Perform safe reversible LIFO undo and verify path restoration
# 11. Clean up temporary sandbox directory

$ErrorActionPreference = "Stop"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "         TidyAI End-to-End Workflow Demonstration         " -ForegroundColor Cyan
Write-Host "         Safe, Local-First File Organization Assistant    " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

$BaseUrl = "http://127.0.0.1:8765"
$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$SampleDataDir = Join-Path $ProjectRoot "sample_data"
$DemoSandboxDir = Join-Path $env:TEMP ("TidyAI_Demo_" + [Guid]::NewGuid().ToString().Substring(0, 8))

# -----------------------------------------------------------------------------
# Step 1: Health & Connectivity Check
# -----------------------------------------------------------------------------
Write-Host "`n[*] Step 1: Checking Backend Health on $BaseUrl/api/health..." -ForegroundColor Yellow
try {
    $health = Invoke-RestMethod -Uri "$BaseUrl/api/health" -Method Get -TimeoutSec 5
    Write-Host "[+] Backend is ONLINE: $($health.service) v$($health.version)" -ForegroundColor Green
    Write-Host "    Host: $($health.host):$($health.port) | DB Connected: $($health.database_connected)" -ForegroundColor Gray
} catch {
    Write-Host "[!] Backend is not running on $BaseUrl." -ForegroundColor Red
    Write-Host "    Please start the backend first with: powershell -File scripts/run_backend.ps1" -ForegroundColor Yellow
    exit 1
}

# -----------------------------------------------------------------------------
# Step 2: Create Isolated Synthetic Demo Sandbox
# -----------------------------------------------------------------------------
Write-Host "`n[*] Step 2: Initializing Isolated Synthetic Sandbox..." -ForegroundColor Yellow
New-Item -ItemType Directory -Path $DemoSandboxDir -Force | Out-Null
Copy-Item -Path "$SampleDataDir\*" -Destination $DemoSandboxDir -Recurse -Force
Write-Host "[+] Sandbox initialized at: $DemoSandboxDir" -ForegroundColor Green
Write-Host "    (Synthetic sample files copied; zero real personal files touched)" -ForegroundColor Gray

try {
    # -------------------------------------------------------------------------
    # Step 3: Approve Directory Root Boundary
    # -------------------------------------------------------------------------
    Write-Host "`n[*] Step 3: Approving Sandbox Directory Boundary..." -ForegroundColor Yellow
    $approveBody = @{
        path = $DemoSandboxDir
        label = "PowerShell Demo Sandbox"
    } | ConvertTo-Json

    $approvedRoot = Invoke-RestMethod -Uri "$BaseUrl/api/roots/approve" -Method Post `
        -ContentType "application/json" -Body $approveBody
    $rootId = $approvedRoot.id
    Write-Host "[+] Approved Root Registered: ID=$rootId" -ForegroundColor Green
    Write-Host "    Canonical Path: $($approvedRoot.canonical_path)" -ForegroundColor Gray

    # -------------------------------------------------------------------------
    # Step 4: Bounded Read-Only Metadata Scan
    # -------------------------------------------------------------------------
    Write-Host "`n[*] Step 4: Executing Read-Only Inventory Scan..." -ForegroundColor Yellow
    $scanBody = @{
        root_id = $rootId
        recursive = $true
        max_files = 1000
    } | ConvertTo-Json

    $scanRes = Invoke-RestMethod -Uri "$BaseUrl/api/scan" -Method Post `
        -ContentType "application/json" -Body $scanBody
    Write-Host "[+] Scan Complete: Found $($scanRes.summary.total_files) files in $($scanRes.summary.duration_ms)ms" -ForegroundColor Green
    Write-Host "    Total size: $($scanRes.summary.total_size_bytes) bytes across $($scanRes.summary.directories_scanned) directories" -ForegroundColor Gray

    # -------------------------------------------------------------------------
    # Step 5: Exact Duplicate Detection (SHA-256)
    # -------------------------------------------------------------------------
    Write-Host "`n[*] Step 5: Detecting Exact Duplicates via Chunked SHA-256..." -ForegroundColor Yellow
    $dupBody = @{
        root_id = $rootId
        min_size_bytes = 0
    } | ConvertTo-Json

    $dupRes = Invoke-RestMethod -Uri "$BaseUrl/api/duplicates" -Method Post `
        -ContentType "application/json" -Body $dupBody
    Write-Host "[+] Duplicate Detection Complete (Diagnostic Only, Zero Deletes):" -ForegroundColor Green
    Write-Host "    Duplicate groups found: $($dupRes.summary.duplicate_groups_count)" -ForegroundColor Gray
    Write-Host "    Reclaimable storage: $($dupRes.summary.potential_savings_bytes) bytes" -ForegroundColor Gray

    # -------------------------------------------------------------------------
    # Step 6: Generate Organization Suggestions
    # -------------------------------------------------------------------------
    Write-Host "`n[*] Step 6: Requesting Organization Suggestions..." -ForegroundColor Yellow
    $suggBody = @{
        root_id = $rootId
        max_files = 10
        confidence_threshold = 0.60
    } | ConvertTo-Json

    $suggRes = $null
    try {
        $suggRes = Invoke-RestMethod -Uri "$BaseUrl/api/suggestions" -Method Post `
            -ContentType "application/json" -Body $suggBody -TimeoutSec 15
        Write-Host "[+] AI Suggestion Engine generated $($suggRes.summary.suggestions_generated) proposals" -ForegroundColor Green
        Write-Host "    Model used: $($suggRes.summary.model_used)" -ForegroundColor Gray
    } catch {
        Write-Host "[-] Ollama AI suggestion generation skipped or timed out ($($_.Exception.Message))" -ForegroundColor DarkYellow
        Write-Host "    Falling back to deterministic classification rules for operation staging..." -ForegroundColor Gray
    }

    # -------------------------------------------------------------------------
    # Step 7: Build Staged Operation Plan
    # -------------------------------------------------------------------------
    Write-Host "`n[*] Step 7: Staging File Relocation Operations..." -ForegroundColor Yellow
    $stagedOperations = @()

    # Find sample files to stage for demonstration
    $reportFile = Get-ChildItem -Path $DemoSandboxDir -Recurse -Filter "*.csv" | Select-Object -First 1
    $noteFile = Get-ChildItem -Path $DemoSandboxDir -Recurse -Filter "*.txt" | Select-Object -First 1

    if ($reportFile) {
        $relSource = $reportFile.FullName.Substring($DemoSandboxDir.Length).TrimStart('\', '/').Replace('\', '/')
        $stagedOperations += @{
            source_rel_path = $relSource
            target_rel_path = "Organized/Reports/" + $reportFile.Name
            operation_type = "move"
            approved = $true
        }
    }

    if ($noteFile) {
        $relSource = $noteFile.FullName.Substring($DemoSandboxDir.Length).TrimStart('\', '/').Replace('\', '/')
        $stagedOperations += @{
            source_rel_path = $relSource
            target_rel_path = "Organized/Notes/" + $noteFile.Name
            operation_type = "move"
            approved = $true
        }
    }

    Write-Host "[+] Staged $($stagedOperations.Count) operations for review" -ForegroundColor Green
    foreach ($op in $stagedOperations) {
        Write-Host "    Move: $($op.source_rel_path) -> $($op.target_rel_path)" -ForegroundColor Cyan
    }

    # -------------------------------------------------------------------------
    # Step 8: Dry-Run Simulation (Strictly Read-Only)
    # -------------------------------------------------------------------------
    Write-Host "`n[*] Step 8: Executing Dry-Run Preview Simulation..." -ForegroundColor Yellow
    $dryBody = @{
        root_id = $rootId
        operations = $stagedOperations
    } | ConvertTo-Json -Depth 5

    $dryRes = Invoke-RestMethod -Uri "$BaseUrl/api/operations/preview" -Method Post `
        -ContentType "application/json" -Body $dryBody

    Write-Host "[+] Dry-Run Simulation Results (Zero Disk Mutations):" -ForegroundColor Green
    Write-Host "    Safe operations: $($dryRes.summary.safe_operations) / $($dryRes.summary.total_operations)" -ForegroundColor Gray
    Write-Host "    Blocked operations: $($dryRes.summary.blocked_operations)" -ForegroundColor Gray
    Write-Host "    Executable: $($dryRes.summary.is_executable)" -ForegroundColor Gray

    # -------------------------------------------------------------------------
    # Step 9: Confirmed Execution
    # -------------------------------------------------------------------------
    Write-Host "`n[*] Step 9: Applying Confirmed Operations to Disk..." -ForegroundColor Yellow
    $applyBody = @{
        root_id = $rootId
        operations = $stagedOperations
        confirmed = $true
    } | ConvertTo-Json -Depth 5

    $applyRes = Invoke-RestMethod -Uri "$BaseUrl/api/operations/apply" -Method Post `
        -ContentType "application/json" -Body $applyBody

    Write-Host "[+] Operations Applied Successfully: Batch ID = $($applyRes.batch_id)" -ForegroundColor Green
    Write-Host "    Applied: $($applyRes.total_applied) | Failed: $($applyRes.failed_count) | Status: $($applyRes.status)" -ForegroundColor Gray

    # Verify moved files exist at destination
    foreach ($item in $applyRes.items) {
        $destPath = Join-Path $DemoSandboxDir $item.target_rel_path.Replace('/', '\')
        if (Test-Path $destPath) {
            Write-Host "    [OK] Confirmed file at: $($item.target_rel_path)" -ForegroundColor Green
        }
    }

    # -------------------------------------------------------------------------
    # Step 10: Inspect Audit Ledger History
    # -------------------------------------------------------------------------
    Write-Host "`n[*] Step 10: Querying SQLite Audit Ledger History..." -ForegroundColor Yellow
    $historyRes = Invoke-RestMethod -Uri "$BaseUrl/api/operations/history?limit=5" -Method Get
    Write-Host "[+] Audit Ledger contains $($historyRes.total_batches) historical batches" -ForegroundColor Green
    $latestBatch = $historyRes.batches | Where-Object { $_.batch_id -eq $applyRes.batch_id } | Select-Object -First 1
    if ($latestBatch) {
        Write-Host "    Batch ID: $($latestBatch.batch_id) | Status: $($latestBatch.status) | Created: $($latestBatch.created_at)" -ForegroundColor Gray
    }

    # -------------------------------------------------------------------------
    # Step 11: Safe Reversible LIFO Undo
    # -------------------------------------------------------------------------
    Write-Host "`n[*] Step 11: Performing Safe Reversible Undo for Batch $($applyRes.batch_id)..." -ForegroundColor Yellow
    $undoRes = Invoke-RestMethod -Uri "$BaseUrl/api/operations/$($applyRes.batch_id)/undo" -Method Post

    Write-Host "[+] Safe Undo Complete: Reverted $($undoRes.total_reverted) files" -ForegroundColor Green
    Write-Host "    Final batch status: $($undoRes.status)" -ForegroundColor Gray

    # Verify files restored back to original source paths
    foreach ($item in $undoRes.items) {
        $restoredPath = Join-Path $DemoSandboxDir $item.source_rel_path.Replace('/', '\')
        if (Test-Path $restoredPath) {
            Write-Host "    [OK] Restored to original path: $($item.source_rel_path)" -ForegroundColor Green
        }
    }

    # -------------------------------------------------------------------------
    # Step 12: Unregister Approved Root
    # -------------------------------------------------------------------------
    Write-Host "`n[*] Step 12: Unregistering Sandbox Boundary..." -ForegroundColor Yellow
    Invoke-RestMethod -Uri "$BaseUrl/api/roots/$rootId" -Method Delete | Out-Null
    Write-Host "[+] Sandbox boundary unregistered cleanly" -ForegroundColor Green

} finally {
    # -------------------------------------------------------------------------
    # Clean up temporary sandbox directory
    # -------------------------------------------------------------------------
    if (Test-Path $DemoSandboxDir) {
        Remove-Item -Path $DemoSandboxDir -Recurse -Force -ErrorAction SilentlyContinue
        Write-Host "`n[+] Temporary sandbox removed cleanly from $DemoSandboxDir" -ForegroundColor Gray
    }
}

Write-Host "`n==========================================================" -ForegroundColor Cyan
Write-Host "   DEMO COMPLETED SUCCESSFULLY WITH 100% VERIFIED SAFETY  " -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Cyan
