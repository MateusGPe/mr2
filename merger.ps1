# --- CONFIGURATION ---
$Output = "merged_code.md"
$SourceDir = "./registro/"

# --- FILTER SETTINGS ---
# 1. Allowed file extensions (without the dot). Leave empty @() to include all files.
$AllowedExtensions = @("py")

# 2. Directories to completely ignore (e.g., build folders, git)
$IgnoreDirs = @(".git", "build", "node_modules", "todo", "ImageViewer")

# 3. Specific files to ignore (exact names)
$IgnoreFiles = @("stb_image.h", "IconsFontAwesome6.h", "fa_solid_900.hpp")


# Clear or initialize the output file with UTF8 encoding (freshen up)
$null | Out-File -FilePath $Output -Force -Encoding UTF8

# Get absolute path of source directory for clean relative path calculations
$SourceFullPath = (Get-Item $SourceDir).FullName

# Fetch all files recursively
$AllFiles = Get-ChildItem -Path $SourceDir -Recurse -File

foreach ($File in $AllFiles) {
    # Calculate relative path and normalize to forward slashes for Markdown consistency
    $RelPath = $File.FullName.Substring($SourceFullPath.Length).TrimStart('\','/')
    $RelPathMarkdown = $RelPath -replace '\\', '/'

    # Split path to check if it resides inside an ignored directory
    $PathParts = $RelPathMarkdown -split '/'
    $DirParts = if ($PathParts.Count -gt 1) { $PathParts[0..($PathParts.Count - 2)] } else { @() }

    # 1. Check directory exclusions
    $Skip = $false
    foreach ($Dir in $DirParts) {
        if ($IgnoreDirs -contains $Dir) {
            $Skip = $true
            break
        }
    }
    if ($Skip) { continue }

    # 2. Check specific file exclusions
    if ($IgnoreFiles -contains $File.Name) { continue }

    # 3. Check allowed extensions
    $Ext = $File.Extension.TrimStart('.').ToLower()
    if ($AllowedExtensions.Count -gt 0 -and ($AllowedExtensions -notcontains $Ext)) { continue }

    # --- PROCESS FILE ---
    Write-Host "Processing $RelPathMarkdown..."

    # Determine language for markdown code block
    $Lang = "text"
    switch ($Ext) {
        { $_ -in "cpp", "c", "h", "hpp" } { $Lang = "cpp"; break }
        "py"   { $Lang = "python"; break }
        { $_ -in "js", "jsx" } { $Lang = "javascript"; break }
        { $_ -in "ts", "tsx" } { $Lang = "typescript"; break }
        "sh"   { $Lang = "bash"; break }
        "json" { $Lang = "json"; break }
    }

    # Write Markdown Header
    Add-Content -Path $Output -Value "## $RelPathMarkdown" -Encoding UTF8
    Add-Content -Path $Output -Value "" -Encoding UTF8
    
    # Open Code Block (Using single quotes to avoid PowerShell backtick escaping traps)
    Add-Content -Path $Output -Value ('```' + $Lang) -Encoding UTF8
    Add-Content -Path $Output -Value "// $RelPathMarkdown" -Encoding UTF8
    
    # Append File Content safely
    Get-Content -Path $File.FullName -Raw -Encoding UTF8 | Add-Content -Path $Output -Encoding UTF8
    
    # Close Code Block and Add Spacing
    Add-Content -Path $Output -Value "" -Encoding UTF8
    Add-Content -Path $Output -Value '```' -Encoding UTF8
    Add-Content -Path $Output -Value "" -Encoding UTF8
    Add-Content -Path $Output -Value "---" -Encoding UTF8
    Add-Content -Path $Output -Value "" -Encoding UTF8
}

Write-Host "Done! All files merged into $Output"