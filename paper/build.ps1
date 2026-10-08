# Build paper/main.pdf: regenerate the tables, then pdflatex + bibtex (TeX Live or MiKTeX on PATH).
# Usage (from anywhere): powershell -File paper/build.ps1
$ErrorActionPreference = "Stop"
$paper = $PSScriptRoot
Push-Location (Split-Path $paper -Parent)
try {
    python paper/tables.py
    if ($LASTEXITCODE -ne 0) { throw "paper/tables.py failed" }
} finally { Pop-Location }
foreach ($tool in @("pdflatex", "bibtex")) {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) { throw "$tool not found: install TeX Live or MiKTeX" }
}
Push-Location $paper
try {
    pdflatex -interaction=nonstopmode -halt-on-error main.tex | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "pdflatex failed: see paper/main.log" }
    bibtex main | Out-Null
    pdflatex -interaction=nonstopmode -halt-on-error main.tex | Out-Null
    pdflatex -interaction=nonstopmode -halt-on-error main.tex | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "pdflatex failed: see paper/main.log" }
    Write-Output "wrote $paper\main.pdf"
} finally { Pop-Location }
